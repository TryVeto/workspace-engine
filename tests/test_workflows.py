import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/engine'))
from workspace_engine.providers import Principal,ProviderRegistry
from workspace_engine.workflows import Workflows,WorkflowConflict
class FakeSender:
    def __init__(self):self.calls=0;self.fail=False
    def send(self,body,idempotency_key):
        self.calls+=1
        if self.fail:raise TimeoutError()
        return {'confirmed':True,'providerId':idempotency_key}
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.path=Path(t.name)/'actions.sqlite3'
        self.adapter=FakeSender();self.registry=ProviderRegistry();self.registry.register('messages',self.adapter,{'send':'messages.send'})
        self.owner=Principal('Owner',frozenset({'actions.draft','actions.approve','actions.execute','actions.reconcile','messages.send'}))
        self.actions=Workflows(self.path,self.registry)
    def test_approval_and_execution_are_separate(self):
        action=self.actions.draft(self.owner,'messages','send',{'body':'Fabricated message'},'one')
        self.assertEqual(self.actions.draft(self.owner,'messages','send',{'body':'Fabricated message'},'one')['id'],action['id'])
        with self.assertRaises(WorkflowConflict):self.actions.execute(self.owner,action['id'],0)
        with self.assertRaises(PermissionError):self.actions.approve(Principal('Agent',self.owner.capabilities,True),action['id'],0)
        approved=self.actions.approve(self.owner,action['id'],0);self.assertEqual(self.adapter.calls,0)
        result=self.actions.execute(self.owner,action['id'],approved['revision']);self.assertEqual(result['state'],'confirmed')
        with self.assertRaises(WorkflowConflict):self.actions.execute(self.owner,action['id'],approved['revision'])
        self.assertEqual(self.adapter.calls,1)
    def test_uncertain_side_effect_cannot_be_repeated_after_restart(self):
        action=self.actions.draft(self.owner,'messages','send',{'body':'Fabricated message'},'two');approved=self.actions.approve(self.owner,action['id'],0);self.adapter.fail=True
        with self.assertRaises(WorkflowConflict):self.actions.execute(self.owner,action['id'],approved['revision'])
        restarted=Workflows(self.path,self.registry);unknown=restarted.get(action['id']);self.assertEqual(unknown['state'],'indeterminate')
        with self.assertRaises(WorkflowConflict):restarted.execute(self.owner,action['id'],unknown['revision'])
        self.assertEqual(self.adapter.calls,1)
        result=restarted.reconcile(self.owner,action['id'],unknown['revision'],{'confirmed':True,'evidence':'Provider receipt checked in the fake adapter'})
        self.assertEqual(result['state'],'confirmed')
