"""Run inside an isolated test container, before/after its restart. Never production."""
import http.cookiejar,json,secrets,sqlite3,sys,threading,time,urllib.request
from pathlib import Path
import paho.mqtt.client as mqtt
data=Path('/data');marker=data/'integration-password'
if not marker.exists():marker.write_text(secrets.token_urlsafe(24))
jar=http.cookiejar.CookieJar();http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def request(path,payload=None):
    r=urllib.request.Request('http://127.0.0.1:8080/api/'+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
    return json.load(http.open(r))
request('session',{'password':marker.read_text(),'setup_token':(data/'setup-token').read_text()})
request('config',{'pulse_volume':.01,'debounce_ms':100})
credentials=json.loads((data/'credentials.json').read_text())
stream='gas-meter-integration-test';ack=threading.Event();seen=[]
client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set('sensor',credentials['sensor'])
def connected(c,u,f,r,p):c.subscribe(f'gas/{stream}/ack',qos=1)
def message(c,u,m):seen.append(json.loads(m.payload)['seq']);ack.set()
client.on_connect=connected;client.on_message=message;client.connect('127.0.0.1',1883);client.loop_start();time.sleep(1)
base=int(time.time()/60)-120
phase=sys.argv[1]
if phase=='first':(data/'integration-minute').write_text(str(base))
base=int((data/'integration-minute').read_text())
records=[{'seq':1,'minute':base,'pulses':2,'total':2,'flags':0},{'seq':2,'minute':base+1,'pulses':3,'total':5,'flags':0},{'seq':3,'minute':base+2,'pulses':4,'total':9,'flags':0}]
for event in ([records[0],records[0],records[1]] if phase=='first' else [records[1],records[2],records[2]]):
    ack.clear();client.publish(f'gas/{stream}/event',json.dumps(event),qos=1)
    assert ack.wait(10) and seen[-1]==event['seq'],'Missing application ACK'
client.disconnect();client.loop_stop()
db=sqlite3.connect(data/'gas.sqlite')
count,volume,earliest=db.execute('SELECT COUNT(*),SUM(pulses*volume),MIN(minute) FROM events').fetchone()
assert count==(2 if phase=='first' else 3)
assert abs(volume-(.05 if phase=='first' else .09))<1e-9
assert earliest==base
print(f'PASS {phase}: committed ACK, deduplication, original timestamps; {count} records')
