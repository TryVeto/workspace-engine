#!/usr/bin/env python3
"""Run a configured instance or the deterministic example workspace."""
import argparse
import os
import sys
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'packages/engine'))
from workspace_engine.instance import default_data,demo,load
from workspace_engine.server import make_server
from workspace_engine.adapters.skill_examples import make_preview_server

def main():
    p=argparse.ArgumentParser();p.add_argument('--demo',action='store_true');p.add_argument('--config');p.add_argument('--data');p.add_argument('--port',type=int,default=8988)
    args=p.parse_args();os.umask(0o077)
    if args.demo and args.config:p.error('Choose demo or a private instance')
    if args.demo:config,data=demo(args.data or default_data('demo'))
    elif args.config:
        config,data=load(args.config)
        if args.data:p.error('Set private data_root in the instance config')
    else:p.error('Use --demo or --config. No personal directories are discovered automatically.')
    server=make_server(config,data,args.port);server.workspace.files.start()
    preview=None
    if server.workspace.skill_examples.manifest().get('examples'):
        preview=make_preview_server(server.workspace.skill_examples,config.get('skills_preview_port',0))
        server.workspace.skill_examples.port=preview.server_port
        threading.Thread(target=preview.serve_forever,daemon=True).start()
    print(f'Workspace {server.server_address[0]}:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close()
        if preview:preview.shutdown();preview.server_close()
if __name__=='__main__':main()
