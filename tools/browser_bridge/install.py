#!/usr/bin/env python3
"""Install the Workspace native messaging host for Chrome and Dia on macOS."""
from __future__ import annotations
import argparse, base64, hashlib, json, secrets, shutil, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'packages/engine'))
from workspace_engine.secrets import SecretStore

ROOT=Path(__file__).resolve().parents[2]
EXTENSION=ROOT/'apps/browser-extension'
HOST=ROOT/'tools/browser_bridge/native_host.py'
HOST_NAME='com.workspace.web'
LOCATIONS=[
    Path.home()/'Library/Application Support/Google/Chrome/NativeMessagingHosts',
    Path.home()/'Library/Application Support/Google/ChromeForTesting/NativeMessagingHosts',
    Path.home()/'Library/Application Support/Chromium/NativeMessagingHosts',
    Path.home()/'Library/Application Support/Dia/User Data/NativeMessagingHosts',
]

def extension_id():
    manifest=json.loads((EXTENSION/'manifest.json').read_text())
    raw=base64.b64decode(manifest['key'])
    alphabet='abcdefghijklmnop'
    return ''.join(alphabet[b>>4]+alphabet[b&15] for b in hashlib.sha256(raw).digest()[:16])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workspace-url',default='http://127.0.0.1:18999')
    parser.add_argument('--print-id',action='store_true')
    parser.add_argument('--brand',default='Workspace')
    args=parser.parse_args()
    eid=extension_id()
    if args.print_id:print(eid);return 0
    brand=' '.join(args.brand.split())[:80] or 'Workspace'
    folder=''.join(c for c in brand if c.isalnum() or c in (' ','-','_')).strip() or 'Workspace'
    private_extension=Path.home()/'Library/Application Support'/folder/'Web Extension'
    if private_extension.exists():shutil.rmtree(private_extension)
    shutil.copytree(EXTENSION,private_extension)
    for name in ('manifest.json','popup.html','popup.js'):
        file=private_extension/name;file.write_text(file.read_text().replace('Workspace',brand))
    SecretStore().set_keychain('workspace-web-bridge',secrets.token_urlsafe(48))
    runtime=Path.home()/'Library/Application Support'/folder/'Browser Bridge'
    runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
    private_host=runtime/'native_host.py';shutil.copy2(HOST,private_host);private_host.chmod(0o700)
    wrapper=runtime/'browser-bridge-host'
    wrapper.write_text('#!/bin/sh\nexport WORKSPACE_URL='+json.dumps(args.workspace_url)+'\nexec '+json.dumps(sys.executable)+' '+json.dumps(str(private_host))+'\n')
    wrapper.chmod(0o700)
    manifest={'name':HOST_NAME,'description':'Workspace explicit page capture bridge','path':str(wrapper),'type':'stdio','allowed_origins':[f'chrome-extension://{eid}/']}
    installed=[]
    for directory in LOCATIONS:
        directory.mkdir(parents=True,exist_ok=True)
        target=directory/(HOST_NAME+'.json');target.write_text(json.dumps(manifest,indent=2)+'\n');installed.append(str(target))
    print(json.dumps({'extensionId':eid,'extensionPath':str(private_extension),'nativeHosts':installed},indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
