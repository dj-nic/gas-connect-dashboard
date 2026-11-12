import json, os, secrets, signal, subprocess, sys, time
from pathlib import Path
data=Path('/data');data.mkdir(exist_ok=True)
os.umask(0o077)
creds=data/'credentials.json'
if not creds.exists():creds.write_text(json.dumps({'sensor':secrets.token_urlsafe(32),'backend':secrets.token_urlsafe(32)}))
token=data/'setup-token'
if not token.exists():token.write_text(secrets.token_urlsafe(24))
c=json.loads(creds.read_text())
passwd=data/'mqtt-passwords'
passwd.write_text(''.join(f'{user}:{pw}\n' for user,pw in c.items()))
subprocess.run(['mosquitto_passwd','-U',str(passwd)],check=True)
(data/'mqtt-acl').write_text('user sensor\ntopic write gas/+/event\ntopic write gas/+/status\ntopic read gas/+/ack\ntopic read gas/+/config\nuser backend\ntopic readwrite gas/#\n')
(data/'mosquitto.conf').write_text('listener 1883 0.0.0.0\nallow_anonymous false\nuser root\npassword_file /data/mqtt-passwords\nacl_file /data/mqtt-acl\nlog_dest stdout\n')
children=[subprocess.Popen(['mosquitto','-c','/data/mosquitto.conf']),subprocess.Popen(['uvicorn','app.main:app','--host','0.0.0.0','--port','8080','--no-access-log'])]
def stop(*args):
    for child in children:child.terminate()
    for child in children:
        try:child.wait(timeout=8)
        except subprocess.TimeoutExpired:child.kill()
    sys.exit(0)
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
while all(p.poll() is None for p in children):time.sleep(1)
stop()
