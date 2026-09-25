import copy
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/engine'))
from workspace_engine.instance import demo
from workspace_engine.model import Workspace,Conflict
from workspace_engine.server import make_server,public_instance
from workspace_engine.storage import private_directory
from workspace_engine.providers import Principal,ProviderRegistry
from workspace_engine.security import Sessions
from workspace_engine.adapters.skill_editor import SkillConflict
from workspace_engine.adapters.ai_runtime import LoopbackAIProvider

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.config,self.root=demo(Path(self.temp.name)/'runtime')
        self.app=Workspace(self.config,self.root)
    def test_demo_is_complete_and_repeatable(self):
        items=self.app.catalog()['items']
        self.assertTrue({'prompts','tasks','skills','files','design'}<={i['mode']for i in items})
        self.assertEqual(len([i for i in items if i['mode']=='prompts']),3)
        self.assertEqual(demo(self.root)[0],self.config)
        self.assertEqual(len(self.app.hq.state()['decisions']),1)
        self.assertFalse((self.root/'libraries/prompts/access-token').exists())
    def test_prompt_edit_retry_history_and_creation(self):
        request={'id':'prompts:demo-1','revision':1,'requestId':'prompt-revision-1','body':'A revised fabricated review prompt.'}
        result=self.app.edit(request);self.assertEqual(self.app.edit(request),result)
        self.assertEqual(result['prompt']['promptVersion'],2)
        self.assertEqual(len(self.app.history('prompts:demo-1')),1)
        with self.assertRaises(Conflict):self.app.edit(dict(request,requestId='stale-prompt-id'))
        prompt={'id':'new-demo','title':'New prompt','body':'Fabricated prompt body.'}
        code,created=self.app.prompts.create_prompt(prompt,'Test author','create-prompt-id')
        self.assertEqual(code,201)
        self.assertEqual(self.app.prompts.create_prompt(prompt,'Test author','create-prompt-id'),(code,created))
        self.assertEqual(created['prompt']['approval'],None)
    def test_culture_retry_and_conflict(self):
        request={'id':'culture:clear-updates','requestId':'culture-write','parts':[{'id':'clear-updates','revision':1,'body':'Share evidence and the next action.'}]}
        self.assertEqual(self.app.edit(request),self.app.edit(request))
        self.assertEqual(len(self.app.history('culture:clear-updates')),1)
        with self.assertRaises(Conflict):self.app.edit(dict(request,requestId='culture-stale'))
    def test_workspace_retry_conflict_and_restart(self):
        state=self.app.state();state['name']='Changed demo'
        request={'revision':state['revision'],'state':state,'requestId':'save-1'}
        response=self.app.save(request);self.assertEqual(self.app.save(request),response)
        self.assertEqual(Workspace(self.config,self.root).state()['name'],'Changed demo')
        altered=copy.deepcopy(request);altered['state']['name']='Different'
        with self.assertRaises(Conflict):self.app.save(altered)
        altered['requestId']='save-2'
        with self.assertRaises(Conflict):self.app.save(altered)
    def test_task_retry_and_stale_revision(self):
        task=self.app.providers.call(Principal('test',frozenset({'tasks.read'})),'tasks','list')['tasks'][0]
        request={'id':'tasks:new','task':dict(task,title='Another task'),'revision':0,'requestId':'new-task'}
        first=self.app.edit(copy.deepcopy(request));second=self.app.edit(copy.deepcopy(request));self.assertEqual(first,second)
        rows=self.app.providers.call(Principal('test',frozenset({'tasks.read'})),'tasks','list')
        self.assertEqual(len(rows['tasks']),2)
        request['requestId']='stale'
        with self.assertRaises(Conflict):self.app.edit(request)
    def test_decision_does_not_execute_anything(self):
        before=self.app.hq.record('decision','apollo-scope')
        request={'action':'decision.resolve','version':before['version'],'requestId':'resolve','actor':'Reviewer','record':{'id':before['id'],'answer':before['options'][0]}}
        result=self.app.hq.mutate(request);self.assertEqual(result,self.app.hq.mutate(request))
        self.assertEqual(result['record']['status'],'resolved')
        self.assertNotIn('executed',result['record'])
    def test_skill_exact_bytes_retries_and_path_boundaries(self):
        skill=self.app.skills.listing()['skills'][0];key=skill['id']
        doc=self.app.skill_editor.document(key,'SKILL.md')
        request={'id':key,'file':'SKILL.md','sha256':doc['sha256'],'text':doc['text']+'\nReviewed.\n','requestId':'skill-save'}
        result=self.app.skill_editor.save(request);self.assertEqual(self.app.skill_editor.save(request),result)
        self.assertEqual(Path(doc['path']).read_text(),request['text'])
        request['requestId']='stale'
        with self.assertRaises(SkillConflict):self.app.skill_editor.save(request)
        for name in ('../workspace.json','/etc/passwd','references/../../../workspace.json'):
            with self.assertRaises((ValueError,FileNotFoundError)):self.app.skill_editor.document(key,name)
        link=Path(doc['path']).parent/'references/escape.md';link.symlink_to(self.root/'sources/files/project-brief.md')
        with self.assertRaises((ValueError,FileNotFoundError)):self.app.skill_editor.document(key,'references/escape.md')
    def test_files_require_observed_explicit_roots(self):
        with self.assertRaises(ValueError):self.app.files.permitted(Path(self.temp.name)/'unlisted.txt')
        self.assertEqual(len(self.app.artifacts.listing()['artifacts']),1)
        source=self.root/'sources/files/project-brief.md';self.assertTrue(source.exists())
    def test_data_cannot_live_in_git(self):
        repo=Path(self.temp.name)/'repo';repo.mkdir();(repo/'.git').mkdir()
        with self.assertRaises(ValueError):private_directory(repo/'data')
    def test_provider_capability_boundary(self):
        with self.assertRaises(PermissionError):self.app.providers.call(Principal('reader',frozenset({'tasks.read'})),'tasks','edit',{})
        with self.assertRaises(LookupError):self.app.providers.call(Principal('owner',frozenset({'tasks.write'})),'tasks','__dict__')
    def test_ai_runtime_rejects_non_loopback_endpoints(self):
        for endpoint in ('https://127.0.0.1:8798','http://example.test:8798',('http://'+'user:pass@'+'127.0.0.1:8798')):
            with self.assertRaises(ValueError):LoopbackAIProvider(endpoint)

    def test_public_config_is_an_allowlist(self):
        public=public_instance({'name':'Demo','owner':'Ada','agents':{'private':{}},'artifact_store':{'password':'placeholder'}})
        self.assertEqual(set(public),{'name','owner','assistantUrl','aiConfigured','version'})
        self.assertFalse(public['aiConfigured'])

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        config,root=demo(Path(self.temp.name)/'runtime')
        self.secret='test-'+os.urandom(24).hex()
        self.patch=patch.dict(os.environ,{'WORKSPACE_TEST_AGENT':self.secret});self.patch.start();self.addCleanup(self.patch.stop)
        config['agents']={'Review agent':{'secretRef':'env:WORKSPACE_TEST_AGENT','capabilities':['workspace.read','decisions.request','updates.write','search.read']}}
        self.server=make_server(config,root,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)
        self.origin='http://127.0.0.1:'+str(self.server.server_port)
        code,data,headers=self.request('GET','/api/state');self.assertEqual(code,200)
        self.token=data['token'];self.cookie=headers['Set-Cookie'].split(';')[0]
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,method,path,data=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        raw=json.dumps(data)if data is not None else None
        h={'Content-Type':'application/json'}if raw is not None else{}
        h.update(headers or {})
        conn.request(method,path,raw,h);response=conn.getresponse();body=response.read();out=dict(response.getheaders());code=response.status;conn.close()
        try:body=json.loads(body)
        except ValueError:pass
        return code,body,out
    def browser(self):return {'Cookie':self.cookie,'Origin':self.origin,'X-Workspace-Token':self.token}
    def test_host_origin_csrf_and_read_session(self):
        for headers in ({'Host':'hostile.example.com'},{'Origin':'https://hostile.example.com'},{'Sec-Fetch-Site':'cross-site'}):
            self.assertEqual(self.request('GET','/api/state',headers=headers)[0],403)
        self.assertEqual(self.request('GET','/api/catalog')[0],401)
        state=self.server.workspace.state();request={'revision':state['revision'],'state':state,'requestId':'http-save'}
        for headers in ({'Cookie':self.cookie},{**self.browser(),'X-Workspace-Token':'wrong'}):
            self.assertEqual(self.request('POST','/api/workspace',request,headers)[0],403)
        self.assertEqual(self.request('POST','/api/workspace',request,self.browser())[0],200)
        self.assertEqual(self.request('POST','/api/workspace',request,self.browser())[0],200)
    def test_bearer_capabilities_and_actor_are_enforced(self):
        headers={'Authorization':'Bearer '+self.secret}
        code,catalog,_=self.request('GET','/api/catalog',headers=headers);self.assertEqual(code,200)
        self.assertFalse(any(i['mode']in ('files','prompts','skills','tasks')for i in catalog['items']))
        self.assertEqual(self.request('GET','/api/export',headers=headers)[0],403)
        self.assertEqual(self.request('GET','/api/state',headers={**headers,'Origin':self.origin})[0],403)
        update={'requestId':'agent-update','action':'update.create','actor':'Spoofed owner','record':{'title':'Review complete','body':'Test update'}}
        code,result,_=self.request('POST','/api/hq',update,headers);self.assertEqual(code,200)
        self.assertEqual(result['record']['actor'],'Review agent')
        update['action']='decision.resolve'
        self.assertEqual(self.request('POST','/api/hq',update,headers)[0],403)
    def test_static_allowlist_security_headers_and_no_credentials(self):
        code,body,headers=self.request('GET','/');self.assertEqual(code,200)
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        for path in ('/.git/config','/server.py','/config.local.json','/../server.py'):
            self.assertEqual(self.request('GET',path)[0],404)
        for path in ('/api/export','/instance.js','/api/catalog','/api/providers'):
            code,body,_=self.request('GET',path,headers={'Cookie':self.cookie});self.assertEqual(code,200)
            self.assertNotIn(self.secret,str(body));self.assertNotIn('WORKSPACE_TEST_AGENT',str(body))
    def test_search_respects_record_capabilities(self):
        code,result,_=self.request('GET','/api/search?q=review',headers={'Authorization':'Bearer '+self.secret})
        self.assertEqual(code,200);self.assertFalse(any(r['id'].startswith(('prompts:','tasks:','skills:','files:'))for r in result['results']))
    def test_skill_runs_http_scope_and_review_boundary(self):
        headers={'Authorization':'Bearer '+self.secret}
        body={'action':'prepare','requestId':'http-run-prepare','runId':'http-run','skillId':'skl_demo_product_review','task':'Review the demo','client':'Demo client'}
        self.assertEqual(self.request('POST','/api/skill-runs',body,headers)[0],403)
        self.server.sessions.agents['Review agent']['capabilities']+=['skills.report','skills.read','skills.review']
        code,run,_=self.request('POST','/api/skill-runs',body,headers)
        self.assertEqual(code,200);self.assertEqual(run['actor'],'Review agent')
        for action,extra in [('read',{}),('reported_applied',{}),('result_returned',{'artifactId':'artifact-http-demo'})]:
            event={'action':action,'runId':'http-run','requestId':'http-run-'+action,**extra}
            self.assertEqual(self.request('POST','/api/skill-runs',event,headers)[0],200)
        event={'action':'result_reviewed','runId':'http-run','requestId':'http-run-review','outcome':'accepted'}
        self.assertEqual(self.request('POST','/api/skill-runs',event,headers)[0],403)
        self.assertEqual(self.request('POST','/api/skill-runs',event,self.browser())[0],200)
        self.assertEqual(self.request('GET','/api/skill-runs',headers=headers)[0],403)
        self.assertEqual(self.request('GET','/api/insights/skills',headers=self.browser())[1]['skills'][0]['reportedRuns'],1)
    def test_ai_runtime_is_owner_managed(self):
        class FakeAI:
            def status(self):return {'ok':True,'account':{'signedIn':True,'type':'chatgpt'}}
            def login(self):return {'loginId':'login-1','authUrl':'https://auth.example.test'}
            def login_status(self,login_id):return {'loginId':login_id,'status':'completed'}
            def logout(self):return {'ok':True}
        app=self.server.workspace;app.ai=FakeAI()
        app.providers.register('ai',app.ai,{'status':'ai.read','login':'ai.manage','login_status':'ai.read','logout':'ai.manage'})
        code,status,_=self.request('GET','/api/ai/status',headers={'Cookie':self.cookie});self.assertEqual(code,200);self.assertTrue(status['account']['signedIn'])
        code,login,_=self.request('POST','/api/ai',{'action':'login'},self.browser());self.assertEqual(code,200);self.assertEqual(login['loginId'],'login-1')
        self.assertEqual(self.request('GET','/api/ai/login/login-1',headers={'Cookie':self.cookie})[1]['status'],'completed')
        self.assertEqual(self.request('POST','/api/ai',{'action':'logout'},self.browser())[0],200)
        self.assertEqual(self.request('POST','/api/ai',{'action':'login'},{'Authorization':'Bearer '+self.secret})[0],403)

    def test_session_expiry(self):
        sessions=Sessions(ttl=-1);key,csrf=sessions.issue({})
        with self.assertRaises(PermissionError):sessions.principal({'Cookie':'workspace-session='+key})

if __name__=='__main__':unittest.main()
