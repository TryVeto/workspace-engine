#!/usr/bin/env python3
"""Scoped local agent client; credentials are references, never command arguments."""
import argparse,json,sys,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/engine'))
from workspace_engine.secrets import SecretStore
p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=Path);p.add_argument('--agent',required=True);p.add_argument('--url',default='http://127.0.0.1:8988');p.add_argument('--file',type=Path);p.add_argument('path');a=p.parse_args()
u=urlsplit(a.url)
if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost') or u.username or u.password:p.error('Use a loopback HTTP address')
if not a.path.startswith('/api/')or '?' in a.path.split('/api/',1)[0]:p.error('Use an /api/ path')
config=json.loads(a.config.expanduser().read_text());spec=config['agents'][a.agent];secret=SecretStore().get(spec['secretRef'])
if not secret:raise SystemExit('Agent credential unavailable')
body=a.file.read_bytes()if a.file else None
if body is not None:
 request=json.loads(body)
 if not isinstance(request,dict):p.error('Request must be a JSON object')
 body=json.dumps(request).encode()
request=urllib.request.Request(a.url.rstrip('/')+a.path,data=body,headers={'Authorization':'Bearer '+secret,'Content-Type':'application/json'})
try:
 with urllib.request.urlopen(request,timeout=30)as response:sys.stdout.buffer.write(response.read()+b'\n')
except urllib.error.HTTPError as error:
 sys.stderr.buffer.write(error.read()+b'\n');raise SystemExit(1)
