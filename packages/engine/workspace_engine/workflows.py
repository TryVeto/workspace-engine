"""Durable approvals for adapter side effects; uncertainty is never retried blindly."""
import hashlib
import json
import uuid
from .storage import connect

class WorkflowConflict(ValueError):pass

class Workflows:
    def __init__(self,path,providers):
        self.path=path;self.providers=providers
        with connect(path)as db:
            db.executescript('CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY, request_id TEXT UNIQUE, digest TEXT, revision INTEGER, state TEXT, body TEXT); CREATE TABLE IF NOT EXISTS action_events(seq INTEGER PRIMARY KEY, id TEXT, state TEXT, actor TEXT, at TEXT DEFAULT CURRENT_TIMESTAMP);')
    def get(self,key):
        with connect(self.path)as db:
            row=db.execute('SELECT revision,state,body FROM actions WHERE id=?',(key,)).fetchone()
        if not row:raise ValueError('Unknown action')
        return dict(json.loads(row[2]),revision=row[0],state=row[1])
    def draft(self,principal,provider,operation,arguments,request_id):
        principal.require('actions.draft')
        if not isinstance(arguments,dict)or not isinstance(request_id,str)or not 0<len(request_id)<=200:raise ValueError('Invalid draft')
        if operation not in self.providers.describe().get(provider,{}):raise ValueError('Unknown adapter operation')
        # The author must have the underlying capability, in addition to drafting.
        principal.require(self.providers.describe()[provider][operation])
        body={'id':str(uuid.uuid4()),'provider':provider,'operation':operation,'arguments':arguments,'author':principal.name}
        digest=hashlib.sha256(json.dumps([provider,operation,arguments,principal.name],sort_keys=True).encode()).hexdigest()
        with connect(self.path)as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT id,digest FROM actions WHERE request_id=?',(request_id,)).fetchone()
            if prior:
                if prior[1]!=digest:raise WorkflowConflict('Request ID reused')
                return self.get(prior[0])
            db.execute('INSERT INTO actions VALUES(?,?,?,0,?,?)',(body['id'],request_id,digest,'drafted',json.dumps(body)))
            db.execute('INSERT INTO action_events(id,state,actor)VALUES(?,?,?)',(body['id'],'drafted',principal.name))
        return self.get(body['id'])
    def approve(self,principal,key,revision):
        principal.require('actions.approve')
        if principal.agent:raise PermissionError('A person must approve this action')
        with connect(self.path)as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute('UPDATE actions SET state="approved",revision=revision+1 WHERE id=? AND revision=? AND state="drafted"',(key,revision))
            if changed.rowcount!=1:raise WorkflowConflict('Action changed or is not a draft')
            db.execute('INSERT INTO action_events(id,state,actor)VALUES(?,?,?)',(key,'approved',principal.name))
        return self.get(key)
    def execute(self,principal,key,revision):
        principal.require('actions.execute');action=self.get(key)
        principal.require(self.providers.describe()[action['provider']][action['operation']])
        with connect(self.path)as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute('UPDATE actions SET state="executing",revision=revision+1 WHERE id=? AND revision=? AND state="approved"',(key,revision))
            if changed.rowcount!=1:raise WorkflowConflict('Action is not approved for execution')
            db.execute('INSERT INTO action_events(id,state,actor)VALUES(?,?,?)',(key,'executing',principal.name))
        try:
            # Every side-effect adapter accepts this stable operation identity.
            receipt=self.providers.call(principal,action['provider'],action['operation'],**action['arguments'],idempotency_key=key)
            if not isinstance(receipt,dict)or receipt.get('confirmed')is not True:raise ValueError('Adapter did not confirm the result')
            serialized=json.dumps(receipt)
            if len(serialized)>100000:raise ValueError('Receipt exceeds the limit')
        except Exception:
            with connect(self.path)as db:
                db.execute('UPDATE actions SET state="indeterminate",revision=revision+1 WHERE id=? AND state="executing"',(key,))
                db.execute('INSERT INTO action_events(id,state,actor)VALUES(?,?,?)',(key,'indeterminate',principal.name))
            raise WorkflowConflict('Result unknown. Reconcile with the provider before attempting another action.')from None
        action['receipt']=receipt
        for k in ('state','revision'):action.pop(k,None)
        with connect(self.path)as db:
            db.execute('UPDATE actions SET state="confirmed",revision=revision+1,body=? WHERE id=? AND state="executing"',(json.dumps(action),key))
            db.execute('INSERT INTO action_events(id,state,actor)VALUES(?,?,?)',(key,'confirmed',principal.name))
        return self.get(key)
    def reconcile(self,principal,key,revision,receipt):
        principal.require('actions.reconcile')
        if principal.agent:raise PermissionError('A person must reconcile this result')
        if not isinstance(receipt,dict)or receipt.get('confirmed')is not True or not receipt.get('evidence'):raise ValueError('Confirmed provider evidence is required')
        with connect(self.path)as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT body FROM actions WHERE id=? AND revision=? AND state IN ("executing","indeterminate")',(key,revision)).fetchone()
            if not row:raise WorkflowConflict('Action is not awaiting reconciliation')
            body=json.loads(row[0]);body['receipt']=receipt
            db.execute('UPDATE actions SET state="confirmed",revision=revision+1,body=? WHERE id=?',(json.dumps(body),key))
            db.execute('INSERT INTO action_events(id,state,actor)VALUES(?,?,?)',(key,'confirmed',principal.name))
        return self.get(key)
