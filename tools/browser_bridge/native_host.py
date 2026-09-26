#!/usr/bin/env python3
"""Chrome/Dia native messaging host for explicit, user-triggered page capture."""
import json, os, struct, sys, urllib.request, uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'packages/engine'))
from workspace_engine.secrets import SecretStore

SERVICE='workspace-engine';ACCOUNT='workspace-web-bridge'
WORKSPACE=os.environ.get('WORKSPACE_URL','http://127.0.0.1:18999').rstrip('/')

def secret():
    value=SecretStore().get('keychain:'+ACCOUNT)
    if not value:raise RuntimeError('Workspace web bridge is not installed')
    return value

def call(payload):
    if payload.get('type')!='capture':
        raise ValueError('Unsupported browser bridge action')
    body=json.dumps({'action':'capture','requestId':payload.get('requestId') or str(uuid.uuid4()),'record':payload.get('record') or {}}).encode()
    req=urllib.request.Request(WORKSPACE+'/api/web',data=body,method='POST',headers={'Content-Type':'application/json','Authorization':'Bearer '+secret()})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req,timeout=12) as r:return json.loads(r.read())

def read_message():
    head=sys.stdin.buffer.read(4)
    if not head:return None
    size=struct.unpack('<I',head)[0]
    if size<=0 or size>8_000_000:raise ValueError('Invalid native message size')
    raw=sys.stdin.buffer.read(size)
    if len(raw)!=size:raise ValueError('Incomplete native message')
    return json.loads(raw)

def write_message(value):
    raw=json.dumps(value,separators=(',',':')).encode()
    sys.stdout.buffer.write(struct.pack('<I',len(raw)));sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()

def main():
    while True:
        try:
            message=read_message()
            if message is None:return 0
            result=call(message);write_message({'ok':True,**result})
        except Exception as exc:
            write_message({'ok':False,'error':str(exc)})
if __name__=='__main__':raise SystemExit(main())
