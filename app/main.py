import hashlib, hmac, json, os, secrets, sqlite3, threading, time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import paho.mqtt.client as mqtt

DATA=Path(os.environ.get('DATA_DIR','/data'))
DATA.mkdir(parents=True,exist_ok=True)
TZ=ZoneInfo('Europe/Berlin')
lock=threading.RLock()
db=sqlite3.connect(DATA/'gas.sqlite',check_same_thread=False)
db.row_factory=sqlite3.Row
db.executescript('''PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
CREATE TABLE IF NOT EXISTS events(stream TEXT, seq INTEGER, minute INTEGER, pulses INTEGER, total INTEGER, flags INTEGER, volume REAL, received INTEGER, PRIMARY KEY(stream,seq));
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS devices(stream TEXT PRIMARY KEY,status TEXT,seen INTEGER);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,expires INTEGER);
''')
def get(key,default=None):
    with lock:
        r=db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return json.loads(r[0]) if r else default
def put(key,value):
    db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,json.dumps(value)))

def ingest(stream,event):
    if not get('configured',False):raise ValueError('Set pulse volume before accepting measurements')
    if not stream.startswith('gas-meter-') or len(stream)>100: raise ValueError('stream')
    fields={k:event[k] for k in ('seq','minute','pulses','total','flags')}
    if any(type(v) is not int or v<0 or v>4294967295 for v in fields.values()):raise ValueError('invalid integer')
    if not fields['seq'] or fields['pulses']>65535 or fields['total']<fields['pulses']:raise ValueError('invalid count')
    if fields['minute'] and not 28333333<=fields['minute']<=int(time.time()/60)+5:raise ValueError('clock')
    with lock,db:
        old=db.execute('SELECT * FROM events WHERE stream=? AND seq=?',(stream,fields['seq'])).fetchone()
        if old and any(old[k]!=v for k,v in fields.items()):raise ValueError('sequence collision')
        if not old:
            prior=db.execute('SELECT total,seq FROM events WHERE stream=? AND seq<? ORDER BY seq DESC LIMIT 1',(stream,fields['seq'])).fetchone()
            if prior and fields['total']<prior[0]:raise ValueError('counter reversal')
            if prior and prior['seq']+1==fields['seq'] and prior['total']+fields['pulses']!=fields['total']:raise ValueError('inconsistent count')
            volume=get('pulse_volume',0.01)
            db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?)',(stream,*fields.values(),volume,int(time.time())))
    return fields['seq']

def on_connect(client,userdata,flags,rc,properties):
    client.subscribe('gas/+/event',qos=1);client.subscribe('gas/+/status',qos=1)
def on_message(client,userdata,msg):
    try:
        _,stream,kind=msg.topic.split('/')
        payload=json.loads(msg.payload)
        if kind=='event':
            if not get('configured',False):return
            seq=ingest(stream,payload)
            client.publish(f'gas/{stream}/ack',json.dumps({'seq':seq}),qos=1)
        elif kind=='status' and stream.startswith('gas-meter-'):
            with lock,db:db.execute('INSERT OR REPLACE INTO devices VALUES (?,?,?)',(stream,json.dumps(payload),int(time.time())))
            client.publish(f'gas/{stream}/config',json.dumps({'debounce_ms':get('debounce_ms',100)}),qos=1,retain=True)
    except (ValueError,KeyError,TypeError,sqlite3.Error):
        # Rejected events are never acknowledged; the device keeps its copy.
        import logging;logging.exception('Rejected gas message')

client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='gas-dashboard')
client.on_connect=on_connect;client.on_message=on_message
@asynccontextmanager
async def life(app):
    cred=json.loads((DATA/'credentials.json').read_text())
    client.username_pw_set('backend',cred['backend'])
    client.connect_async('127.0.0.1',1883);client.loop_start()
    yield
    client.disconnect();client.loop_stop()
app=FastAPI(lifespan=life)

@app.middleware('http')
async def security(request,call_next):
    public=request.url.path in ('/','/health','/api/session','/api/setup') or request.url.path.startswith('/static/')
    if not public:
        token=request.cookies.get('gas_session','')
        with lock:r=db.execute('SELECT expires FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not r or r[0]<time.time():return JSONResponse({'detail':'Bitte anmelden'},status_code=401)
    if request.method not in ('GET','HEAD'):
        origin=request.headers.get('origin')
        if origin and origin not in (f'http://{request.headers.get("host")}',f'https://{request.headers.get("host")}'):
            return JSONResponse({'detail':'Origin abgelehnt'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
    return response

@app.get('/health')
def health():return {'ok':True,'mqtt':client.is_connected()}
@app.get('/')
def root():return FileResponse(Path(__file__).parent/'static/index.html')
app.mount('/static',StaticFiles(directory=Path(__file__).parent/'static'),name='static')

@app.get('/api/session')
def session(request:Request):
    token=request.cookies.get('gas_session','')
    with lock:r=db.execute('SELECT expires FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    return {'setup':get('auth') is None,'authenticated':bool(r and r[0]>time.time())}

attempts={}
@app.post('/api/session')
async def login(request:Request):
    ip=request.client.host; now=time.time();recent=[x for x in attempts.get(ip,[]) if x>now-300]
    if len(recent)>=10:raise HTTPException(429,'Bitte fünf Minuten warten')
    attempts[ip]=recent+[now]
    body=await request.json();password=body.get('password','');stored=get('auth')
    if type(password) is not str or len(password)>200:raise HTTPException(400,'Ungültiges Passwort')
    if not stored:
        # First owner must possess the randomly generated, server-local setup token.
        setup_token=(DATA/'setup-token').read_text().strip()
        if not hmac.compare_digest(str(body.get('setup_token','')),setup_token):raise HTTPException(403,'Einrichtungscode fehlt oder stimmt nicht')
        if len(password)<12:raise HTTPException(400,'Mindestens 12 Zeichen verwenden')
        salt=secrets.token_hex(16)
        with lock,db:put('auth',{'salt':salt,'hash':hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()})
    else:
        hashed=hashlib.scrypt(password.encode(),salt=stored['salt'].encode(),n=16384,r=8,p=1).hex()
        if not hmac.compare_digest(hashed,stored['hash']):raise HTTPException(403,'Passwort stimmt nicht')
    token=secrets.token_urlsafe(32)
    with lock,db:
        db.execute('DELETE FROM sessions WHERE expires<?',(now,))
        db.execute('INSERT INTO sessions VALUES (?,?)',(hashlib.sha256(token.encode()).hexdigest(),int(now+86400)))
    attempts.pop(ip,None)
    response=JSONResponse({'ok':True})
    response.set_cookie('gas_session',token,max_age=86400,httponly=True,samesite='strict')
    return response

@app.delete('/api/session')
def logout(request:Request):
    with lock,db:db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(request.cookies.get('gas_session','').encode()).hexdigest(),))
    response=JSONResponse({'ok':True});response.delete_cookie('gas_session');return response

@app.get('/api/setup')
def setup_help():return {'message':'Einrichtungscode auf dem Server: docker exec gas-connect cat /data/setup-token'}

@app.get('/api/config')
def config():
    return {'configured':get('configured',False),'pulse_volume':get('pulse_volume',.01),'debounce_ms':get('debounce_ms',100),'offset':get('offset',0),'price':get('price',0)}
@app.post('/api/config')
async def change_config(request:Request):
    data=await request.json()
    with lock,db:
        if 'pulse_volume' in data:
            value=float(data['pulse_volume'])
            if value not in (.001,.01,.1,1):raise HTTPException(400,'Ungültiger Impulswert')
            if db.execute('SELECT 1 FROM events WHERE pulses>0 LIMIT 1').fetchone() and value!=get('pulse_volume',.01):raise HTTPException(400,'Impulswert vor Beginn der Messung festlegen; bestehende Historie bleibt geschützt.')
            put('pulse_volume',value)
            put('configured',True)
        if 'debounce_ms' in data:
            value=int(data['debounce_ms'])
            if not 10<=value<=1000:raise HTTPException(400,'Entprellzeit: 10–1000 ms')
            put('debounce_ms',value)
        if 'price' in data:
            value=float(data['price'])
            if not 0<=value<=1000:raise HTTPException(400,'Ungültiger Preis')
            put('price',value)
        if 'meter_reading' in data:
            value=float(data['meter_reading'])
            if not 0<=value<=99999999:raise HTTPException(400,'Ungültiger Zählerstand')
            device=db.execute('SELECT status,seen FROM devices ORDER BY seen DESC LIMIT 1').fetchone()
            if not device or time.time()-device['seen']>20:raise HTTPException(400,'Zuerst den Sensor verbinden')
            current=json.loads(device['status'])['total_pulses']
            put('offset',value-current*get('pulse_volume',.01))
    return config()

@app.get('/api/device-setup')
def device_setup():
    cred=json.loads((DATA/'credentials.json').read_text())
    return {'username':'sensor','password':cred['sensor'],'port':1883,'setup':'Gas-Setup-<Suffix>; Passwort gas-<Suffix>; http://192.168.4.1'}

@app.get('/api/dashboard')
def dashboard(days:int=1):
    if days not in (1,7,30,365):raise HTTPException(400,'Zeitraum ungültig')
    now=int(time.time());local=datetime.now(TZ)
    starts={
      'today':int(local.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()/60),
      'month':int(local.replace(day=1,hour=0,minute=0,second=0,microsecond=0).timestamp()/60),
      'year':int(local.replace(month=1,day=1,hour=0,minute=0,second=0,microsecond=0).timestamp()/60)}
    with lock:
        totals={k:db.execute('SELECT COALESCE(SUM(pulses*volume),0) FROM events WHERE minute>=?',(v,)).fetchone()[0] for k,v in starts.items()}
        from datetime import timedelta
        yesterday=int((local.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=1)).timestamp()/60)
        totals['yesterday']=db.execute('SELECT COALESCE(SUM(pulses*volume),0) FROM events WHERE minute>=? AND minute<?',(yesterday,starts['today'])).fetchone()[0]
        interval=5 if days==1 else 60 if days<=30 else 1440
        rows=db.execute('SELECT (minute / ?)*? AS minute,SUM(pulses*volume) AS volume FROM events WHERE minute>=? GROUP BY 1 ORDER BY 1',(interval,interval,int(now/60)-days*1440)).fetchall()
        latest=db.execute('SELECT total,stream,seq FROM events ORDER BY received DESC,seq DESC LIMIT 1').fetchone()
        devices=[{**json.loads(r['status']),'seen':r['seen']} for r in db.execute('SELECT * FROM devices')]
        unknown=db.execute('SELECT COALESCE(SUM(pulses*volume),0) FROM events WHERE minute=0').fetchone()[0]
    volume=get('pulse_volume',.01)
    live=devices[0] if devices else {}
    online=now-live.get('seen',0)<20
    current=live.get('total_pulses',latest['total'] if latest else None)
    return {'totals':totals,'reading':(current*volume+get('offset',0)) if current is not None else None,
      'flow':live.get('pulses_per_hour',0)*volume if online else None,'online':online,
      'devices':devices,'series':[dict(x) for x in rows],'interval':interval,'days':days,
      'mqtt':client.is_connected(),'price':get('price',0),'unknown_volume':unknown,'has_data':bool(latest)}
