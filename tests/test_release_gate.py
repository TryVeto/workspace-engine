import importlib.util
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('release_gate',Path(__file__).resolve().parents[1]/'tools/release_gate.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
class ReleaseTests(unittest.TestCase):
    def test_private_files_and_content(self):
        samples=[('.env.production',b'anything'),('fixture.sqlite3',b'data'),('screen.png',b'fake'),('test.json',('name'+'@'+'private.test').encode()),('test.md',('/'+'Users'+'/someone/file').encode()),('test.txt',('gh'+'p_'+'a'*36).encode()),('fixture.md',('https://'+'internal'+'.private.test/project').encode())]
        for name,content in samples:
            with self.subTest(name=name):self.assertTrue(gate.inspect(name,content))
    def test_fake_content_and_notice(self):
        self.assertFalse(gate.inspect('example.md',b'Ada Lovelace at Northstar Studio: https://example.com'))
    def test_deleted_secret_is_still_rejected(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
            def git(*args):return subprocess.run(['git','-C',tmp,*args],capture_output=True,check=True,env=env)
            git('init','-q');git('config','user.name','Test');git('config','user.email','test@example.test')
            (root/'fixture.txt').write_text('gh'+'p_'+'a'*36);git('add','.');git('commit','-qm','First fixture')
            (root/'fixture.txt').unlink();git('add','-u');git('commit','-qm','Remove fixture')
            self.assertFalse(gate.scan(root));self.assertTrue(gate.scan(root,history=True))
    def test_private_policy_stays_external(self):
        self.assertTrue(gate.inspect('fixture.md',b'private-sentinel',{'denyPatterns':['private-sentinel']}))
    def test_policy_can_allow_one_exact_historical_finding(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
            subprocess.run(['git','-C',tmp,'init','-q'],check=True,env=env);subprocess.run(['git','-C',tmp,'config','user.name','Private Name'],check=True,env=env);subprocess.run(['git','-C',tmp,'config','user.email','private@example.test'],check=True,env=env)
            (root/'ok.md').write_text('safe');subprocess.run(['git','-C',tmp,'add','.'],check=True,env=env);subprocess.run(['git','-C',tmp,'commit','-qm','Fixture'],check=True,env=env)
            commit=subprocess.run(['git','-C',tmp,'rev-parse','HEAD'],capture_output=True,text=True,check=True,env=env).stdout.strip()
            policy={'denyPatterns':['Private Name'],'allowFindings':[{'name':'commit-'+commit+'.txt','reason':'private policy match'}]}
            self.assertFalse(any(reason=='private policy match' for _,reason in gate.scan(root,history=True,policy=policy)))
