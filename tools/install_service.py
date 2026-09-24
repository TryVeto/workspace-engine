#!/usr/bin/env python3
"""Install an explicit private instance as a restartable macOS user service."""
import argparse,os,plistlib,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'packages/engine'))
from workspace_engine.instance import load
p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--port',type=int,default=8988);p.add_argument('--name',default='default');a=p.parse_args()
if sys.platform!='darwin':p.error('This installer supports macOS user services')
if not a.name.replace('-','').isalnum():p.error('Use letters, digits, and hyphens for the name')
load(a.config)
label='org.workspace.'+a.name;target=Path.home()/'Library/LaunchAgents'/(label+'.plist')
if target.exists():p.error('Service already exists; inspect it before replacing')
logs=Path.home()/'Library/Logs/Workspace';logs.mkdir(parents=True,exist_ok=True,mode=0o700)
service={'Label':label,'ProgramArguments':[sys.executable,str(root/'server.py'),'--config',str(a.config.expanduser().resolve()),'--port',str(a.port)],'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':10,'StandardOutPath':str(logs/(a.name+'.log')),'StandardErrorPath':str(logs/(a.name+'-error.log'))}
target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(plistlib.dumps(service));os.chmod(target,0o600)
subprocess.run(['launchctl','bootstrap','gui/'+str(os.getuid()),str(target)],check=True)
print('Installed '+label)
