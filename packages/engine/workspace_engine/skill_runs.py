"""Explicit skill usage and human-reviewed outcomes, separate from file access."""
import datetime, hashlib, json, re
from .storage import connect
from .skill_identity import package_revision

STAGES = ("prepared", "read", "reported_applied", "result_returned", "result_reviewed")
OUTCOMES = ("accepted", "revised", "rejected")
def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
def text(value, field, limit=200, required=True):
    if not isinstance(value, str) or len(value)>limit or (required and not value.strip()):
        raise ValueError("Invalid " + field)
    return value.strip()
class RunConflict(ValueError): pass

class SkillRuns:
    def __init__(self, path, catalog):
        self.path, self.catalog = path, catalog
        with connect(path) as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS skill_runs(
              id TEXT PRIMARY KEY, skill_id TEXT NOT NULL, revision TEXT NOT NULL,
              title TEXT NOT NULL, task_id TEXT, task TEXT NOT NULL, client TEXT NOT NULL,
              actor TEXT NOT NULL, instructions TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS skill_run_events(
              id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES skill_runs(id),
              stage TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL,
              artifact TEXT, outcome TEXT, UNIQUE(run_id,stage));
            CREATE TABLE IF NOT EXISTS skill_run_receipts(
              id TEXT PRIMARY KEY, payload TEXT NOT NULL, response TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS skill_run_identity ON skill_runs(skill_id,created);
            """)

    def _run(self, db, run_id, instructions=False):
        row=db.execute("SELECT * FROM skill_runs WHERE id=?", (run_id,)).fetchone()
        if row is None: raise FileNotFoundError("Run not found")
        keys=("id","skillId","revision","title","taskId","task","client","actor","instructions","createdAt")
        result=dict(zip(keys,row))
        if not instructions:result.pop("instructions")
        result["events"]=[dict(zip(("eventId","stage","actor","at","artifactId","outcome"),x))
            for x in db.execute("SELECT id,stage,actor,at,artifact,outcome FROM skill_run_events WHERE run_id=? ORDER BY at,id",(run_id,))]
        return result

    def apply(self, request, principal):
        request_id=text(request.get("requestId"),"requestId")
        action=request.get("action")
        allowed={"prepare","read","reported_applied","result_returned","result_reviewed"}
        if action not in allowed:raise ValueError("Unknown skill run action")
        principal.require("skills.review" if action=="result_reviewed" else "skills.report")
        if action in ("prepare","read"):principal.require("skills.read")
        if action=="result_reviewed" and principal.agent:
            raise PermissionError("A person must review returned work")
        fields={"requestId","action","runId","skillId","revision","taskId","task","client","artifactId","outcome"}
        if set(request)-fields:raise ValueError("Unknown skill run field")
        run_id=text(request.get("runId"),"runId")
        payload=json.dumps({"request":request,"actor":principal.name,"agent":principal.agent},sort_keys=True)
        digest=hashlib.sha256(payload.encode()).hexdigest()
        with connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            receipt=db.execute("SELECT payload,response FROM skill_run_receipts WHERE id=?",(request_id,)).fetchone()
            if receipt:
                if receipt[0]!=digest:raise RunConflict("This request ID belongs to another event")
                return json.loads(receipt[1])
            artifact,outcome=None,None
            if action=="prepare":
                self.catalog.refresh()
                key=self.catalog.resolve(text(request.get("skillId"),"skillId"))
                skill=self.catalog.items[key]
                if not skill.get("stable"):raise ValueError("Assign a stable skill identity before reporting runs")
                document=self.catalog.document(key)
                revision=skill["revision"]
                if package_revision(skill["_path"])!=revision:raise RunConflict("Skill changed while preparing; retry with a new request")
                if request.get("revision") and request["revision"]!=revision:
                    raise RunConflict("The skill changed. Read its current revision before preparing a run.")
                if db.execute("SELECT 1 FROM skill_runs WHERE id=?",(run_id,)).fetchone():
                    raise RunConflict("This run ID is already in use")
                task=text(request.get("task"),"task",400)
                client=text(request.get("client"),"client",100)
                task_id=text(request.get("taskId",""),"taskId",200,False)
                db.execute("INSERT INTO skill_runs VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (run_id,key,revision,skill.get("label") or skill["name"],task_id,task,client,principal.name,document["text"],now()))
                stage="prepared"
            else:
                run=self._run(db,run_id)
                if principal.agent and run["actor"]!=principal.name:
                    raise PermissionError("Agents may report only their own runs")
                stage=action
                previous={x["stage"] for x in run["events"]}
                required={"read":"prepared","reported_applied":"read","result_returned":"reported_applied","result_reviewed":"result_returned"}[stage]
                if required not in previous:raise RunConflict("Record "+required+" before "+stage)
                if stage=="result_returned":artifact=text(request.get("artifactId"),"artifactId",240)
                if stage=="result_reviewed":
                    outcome=request.get("outcome")
                    if outcome not in OUTCOMES:raise ValueError("Choose accepted, revised, or rejected")
                existing=next((e for e in run["events"] if e["stage"]==stage),None)
                if existing and (existing["artifactId"]!=artifact or existing["outcome"]!=outcome):
                    raise RunConflict("This stage is already recorded with different evidence")
            db.execute("INSERT OR IGNORE INTO skill_run_events VALUES(?,?,?,?,?,?,?)",
                (request_id,run_id,stage,principal.name,now(),artifact,outcome))
            response=self._run(db,run_id,instructions=action=="read")
            db.execute("INSERT INTO skill_run_receipts VALUES(?,?,?)",(request_id,digest,json.dumps(response)))
            return response

    def listing(self, skill_id=None, run_id=None):
        with connect(self.path) as db:
            if run_id:return {"runs":[self._run(db,run_id)]}
            if skill_id:
                ids=db.execute("SELECT id FROM skill_runs WHERE skill_id=? ORDER BY created DESC LIMIT 200",(skill_id,)).fetchall()
            else:ids=db.execute("SELECT id FROM skill_runs ORDER BY created DESC LIMIT 200").fetchall()
            return {"runs":[self._run(db,x[0]) for x in ids]}

    def insights(self):
        self.catalog.refresh()
        rows={key:{"id":key,"title":s.get("label") or s["name"],"reportedRuns":0,"lastUsed":None,"stable":s.get("stable",False)}
              for key,s in self.catalog.items.items() if s.get("active",True)}
        with connect(self.path) as db:
            for key,title,count,last in db.execute("""
                SELECT r.skill_id,MAX(r.title),COUNT(DISTINCT r.id),MAX(e.at)
                FROM skill_runs r JOIN skill_run_events e ON e.run_id=r.id
                WHERE e.stage='reported_applied' GROUP BY r.skill_id"""):
                rows.setdefault(key,{"id":key,"title":title,"stable":True})
                rows[key].update(reportedRuns=count,lastUsed=last)
        return {"skills":sorted(rows.values(),key=lambda x:(-x["reportedRuns"],x["title"])),
                "coverage":"Reported runs count explicit application reports once per run. Activity outside this path is unknown."}
