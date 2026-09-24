#!/usr/bin/env python3
"""Fail closed on unreviewed files, private identifiers, secrets, and Git history."""
import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TEXT={'.ts','.py','.js','.mjs','.css','.html','.md','.json','.yml','.yaml','.toml','.svg','.txt'}
SPECIAL={'.gitignore','.gitattributes','pre-commit','pre-push','LICENSE','Makefile'}
EMAIL=re.compile(r'[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})')
HOMEPATH=re.compile(r'/(?:Users|home)/[A-Za-z][A-Za-z0-9._-]+')
SECRET=re.compile(r'(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)')
ASSIGN=re.compile(r'''(?i)(?:api[_-]?key|access[_-]?token|password|secret)\s*["']?\s*[:=]\s*["']([A-Za-z0-9_+/=-]{24,})["']''')
URL=re.compile(r'https?://([A-Za-z0-9][A-Za-z0-9.-]*)(?=[:/\s"\'])')
PUBLIC_DOMAINS={'example.com','example.org','example.test','localhost','127.0.0.1','www.w3.org','skill.invalid','github.com','docs.github.com','cheatsheetseries.owasp.org','json-schema.org','spdx.org','apache.org','www.apache.org'}

def git(root,*args,check=True):
    return subprocess.run(['git','-C',str(root),*args],capture_output=True,check=check).stdout

def inspect(name,raw,policy=None):
    findings=[];p=Path(name);lower=name.lower()
    if any(part.startswith('.env') for part in p.parts) or p.name in {'tokens.json','config.local.json','gmail-cache.json','chat.db'}:
        findings.append('private filename')
    if p.suffix not in TEXT and p.name not in SPECIAL:
        findings.append('unreviewed file type')
    if len(raw)>2_000_000:findings.append('oversized file')
    try:body=raw.decode('utf-8')
    except UnicodeDecodeError:return findings+['binary content']
    if '\x00' in body:findings.append('binary content')
    if SECRET.search(body):findings.append('credential signature')
    if HOMEPATH.search(body):findings.append('user home path')
    if any(m.group(1).lower() not in {'example.com','example.org','example.test','users.noreply.github.com'} for m in EMAIL.finditer(body)):
        findings.append('non-fixture email')
    for m in ASSIGN.finditer(body):
        value=m.group(1);entropy=-sum((value.count(c)/len(value))*math.log2(value.count(c)/len(value)) for c in set(value))
        if entropy>3.3:findings.append('credential-like assignment');break
    if any(m.group(1).lower() not in PUBLIC_DOMAINS and not m.group(1).endswith(('.localhost','.example.com','.example.test')) for m in URL.finditer(body)):
        findings.append('unapproved URL host')
    exempt_lines=set((policy or {}).get('allowLines',{}).get(name,[]))
    policy_body='\n'.join(line for line in body.splitlines()if line not in exempt_lines)
    for expression in (policy or {}).get('denyPatterns',[]):
        if re.search(expression,policy_body,re.I):findings.append('private policy match');break
    if p.suffix=='.svg' and (re.search(r'<(?:script|foreignObject)|\bon\w+\s*=|(?:href|src)\s*=',body,re.I)):
        findings.append('active SVG')
    return findings

def scan(root,history=False,staged=False,policy=None):
    findings=[];entries={};seen=set()
    def check(name,raw,mode='100644'):
        if mode not in ('100644','100755'):findings.append((name,'symlink or submodule'));return
        key=(name,hashlib.sha256(raw).hexdigest())
        if key in seen:return
        seen.add(key)
        findings.extend((name,f)for f in inspect(name,raw,policy))
    if staged:
        for line in git(root,'ls-files','--stage','-z').split(b'\0'):
            if not line:continue
            meta,name=line.split(b'\t',1);mode,oid,stage=meta.decode().split();name=name.decode()
            if stage!='0':findings.append((name,'unmerged file'));continue
            check(name,git(root,'cat-file','blob',oid),mode)
    else:
        for p in root.rglob('*'):
            relative=p.relative_to(root)
            if any(x in {'.git','__pycache__','node_modules','.venv'} for x in relative.parts):continue
            if p.is_symlink():findings.append((str(relative),'symlink'));continue
            if p.is_file():check(str(relative),p.read_bytes())
    if history:
        # Include dangling commits and annotated tags: local history never held private data.
        objects=[line.split() for line in git(root,'cat-file','--batch-all-objects','--batch-check=%(objectname) %(objecttype)',check=False).decode().splitlines()]
        commits={oid for oid,kind in objects if kind=='commit'}
        for oid,kind in objects:
            if kind=='tag':check('tag-'+oid+'.txt',git(root,'cat-file','tag',oid))
        for commit in commits:
            metadata=git(root,'show','-s','--format=%an%n%ae%n%cn%n%ce%n%B',commit)
            check('commit-'+commit+'.txt',metadata)
            for line in git(root,'ls-tree','-r','-z',commit).split(b'\0'):
                if not line:continue
                meta,name=line.split(b'\t',1);mode,kind,oid=meta.decode().split();name=name.decode()
                if kind!='blob':findings.append((name,'submodule'));continue
                key=(mode,oid,name)
                if key in entries:continue
                entries[key]=True;check(name,git(root,'cat-file','blob',oid),mode)
    return sorted(set(findings))

def main():
    p=argparse.ArgumentParser();p.add_argument('--history',action='store_true');p.add_argument('--staged',action='store_true');p.add_argument('--policy');p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args()
    policy_path=a.policy or git(a.root,'config','--get','workspace.releasePolicy',check=False).decode().strip()
    policy=json.loads(Path(policy_path).read_text()) if policy_path else None
    findings=scan(a.root,history=a.history,staged=a.staged,policy=policy)
    for name,reason in findings:print(f'{name}: {reason}')
    print(f'Release gate: {len(findings)} finding(s). Values are never printed.')
    raise SystemExit(bool(findings))
if __name__=='__main__':main()
