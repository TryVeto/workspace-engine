"""Instance config is explicit; startup never discovers personal files or credentials."""
import json
import os
import shutil
import sys
from pathlib import Path
from .storage import private_directory, connect

REPOSITORY=Path(__file__).resolve().parents[3]

def default_data(instance='default'):
    if sys.platform=='darwin':base=Path.home()/'Library'/'Application Support'/'Workspace'
    else:base=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local'/'share'))/'workspace'
    return base/instance

def load(path):
    path=Path(path).expanduser().resolve()
    if path.is_relative_to(REPOSITORY):raise ValueError('Private configuration belongs outside the engine checkout')
    raw=json.loads(path.read_text())
    if not isinstance(raw,dict):raise ValueError('Invalid instance configuration')
    allowed={'name','owner','data_root','prompts','culture','tasks','culture_seed','skills_config','file_roots','references','artifact_store','assistant_url','agents','capabilities','host_aliases','session_ttl_seconds','skills_preview_port','knowledge_root','ai_runtime_url'}
    if set(raw)-allowed:raise ValueError('Unknown instance setting')
    def absolute(value):
        p=Path(value).expanduser();return str((path.parent/p).resolve()if not p.is_absolute()else p.resolve())
    for key in ('data_root','prompts','culture','tasks','culture_seed','skills_config','references','knowledge_root'):
        if key in raw:raw[key]=absolute(raw[key])
    raw['file_roots']=[absolute(p)for p in raw.get('file_roots',[])]
    root=private_directory(raw.get('data_root',default_data()),REPOSITORY)
    return raw,root

def demo(data):
    root=private_directory(data,REPOSITORY);marker=root/'demo-instance.json'
    if marker.exists():
        config=json.loads(marker.read_text())
        if config.get('demoVersion')!=1:raise ValueError('Unknown demo instance; use a new data directory')
        return config['config'],root
    if any(root.iterdir()):raise ValueError('Demo initialization requires an empty directory')
    fixtures=REPOSITORY/'examples/demo-workspace';sources=root/'sources';shutil.copytree(fixtures,sources)
    skills=sources/'skills.json';skills.write_text(json.dumps({'roots':[{'path':str(sources/'skills'),'label':'Demo skills','editable':True,'shortcuts':{'review':'1'}}]}))
    config={'name':'Northstar Studio','owner':'Ada Lovelace','skills_config':str(skills),'file_roots':[str(sources/'files')],'references':str(sources/'references.json')}
    from .model import Workspace
    app=Workspace(config,root)
    seed=json.loads((sources/'workspace.json').read_text())
    from .adapters.prompts import pack,digest
    with app.prompts.connect() as db:
        for index,prompt in enumerate(seed['prompts']):
            record={**prompt,'revision':1,'updatedAt':'2026-01-01T00:00:00Z','sha256':digest(prompt['body'])}
            db.execute('INSERT INTO prompts VALUES(?,?,?,?)',(record['id'],index,1,pack(record)))
    with connect(app.config['tasks']) as db:db.execute('UPDATE state SET body=? WHERE id=1',(json.dumps({'revision':0,'tasks':seed['tasks']}),))
    state=app.state();state.update(seed['workspace']);app.save({'revision':state['revision'],'state':state,'requestId':'demo-initial-state'})
    for request in seed['headquarters']:app.hq.mutate(request)
    culture=seed.get('culture',[])
    Path(app.config['culture_seed']).write_text(json.dumps({'entries':[{'id':x['id'],'title':x['title'],'parts':[x['id']],'group':'Working together'}for x in culture]}))
    with connect(app.config['culture'])as db:
        for x in culture:db.execute('INSERT INTO blocks VALUES(?,?,1)',(x['id'],x['body']))
    app.files.scan()
    intake=app.files.inventory()['files']
    if intake:app.artifacts.promote({'fileId':intake[0]['id'],'logicalPath':'Projects/Apollo/'+Path(intake[0]['path']).name})
    marker.write_text(json.dumps({'demoVersion':1,'config':config},indent=2));os.chmod(marker,0o600)
    return config,root
