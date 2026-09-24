#!/usr/bin/env python3
"""Store a credential in macOS Keychain without printing or placing it in argv."""
import argparse,getpass,secrets,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/engine'))
from workspace_engine.secrets import SecretStore
p=argparse.ArgumentParser();p.add_argument('account');p.add_argument('--generate',action='store_true');a=p.parse_args()
value=secrets.token_urlsafe(40)if a.generate else getpass.getpass('Credential: ')
if not value:raise SystemExit('Credential cannot be empty')
SecretStore().set_keychain(a.account,value)
print('Stored. Use secretRef: keychain:'+a.account)
