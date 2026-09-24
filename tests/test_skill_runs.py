import hashlib,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"packages/engine"))
from workspace_engine.adapters.skills import Catalog
from workspace_engine.adapters.skill_editor import SkillEditor
from workspace_engine.skill_runs import SkillRuns,RunConflict
from workspace_engine.providers import Principal
from workspace_engine.knowledge import KnowledgeLibrary

class SkillRunTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.library=self.root/"library";self.skill=self.library/"review";self.skill.mkdir(parents=True)
  (self.skill/"SKILL.md").write_text("---\nname: review\ndescription: Review a product\n---\n# Product review\nInspect the result.")
  (self.skill/"workspace-skill.json").write_text(json.dumps({"id":"skl_test_review","source":"local"}))
  self.catalog=Catalog({"roots":[{"path":str(self.library),"editable":True}]})
  self.runs=SkillRuns(self.root/"runs.sqlite3",self.catalog)
  self.person=Principal("Demo owner",frozenset({"skills.read","skills.report","skills.review"}))
  self.agent=Principal("Demo agent",frozenset({"skills.read","skills.report","skills.review"}),True)
 def tearDown(self):self.temp.cleanup()
 def event(self,action,who=None,**kw):
  return self.runs.apply({"requestId":"event-"+action,"runId":"run-one","action":action,**kw},who or self.agent)
 def prepare(self):
  return self.event("prepare",skillId="skl_test_review",task="Review the fabricated prototype",client="Test client")
 def test_full_causal_chain_and_human_review(self):
  result=self.prepare();revision=result["revision"]
  self.assertEqual(self.event("read")["instructions"],(self.skill/"SKILL.md").read_text())
  self.event("reported_applied");self.event("result_returned",artifactId="artifact-demo-result")
  with self.assertRaises(PermissionError):self.event("result_reviewed",outcome="accepted")
  reviewed=self.event("result_reviewed",who=self.person,outcome="accepted")
  self.assertEqual(reviewed["events"][-1]["outcome"],"accepted")
  self.assertEqual(reviewed["revision"],revision)
  self.assertEqual(self.runs.insights()["skills"][0]["reportedRuns"],1)
 def test_repeat_reads_and_event_replay(self):
  self.prepare();a=self.event("read");b=self.event("read");self.assertEqual(a,b)
  self.runs.apply({"requestId":"another-read","runId":"run-one","action":"read"},self.agent)
  self.assertEqual(len(self.runs.listing()["runs"][0]["events"]),2)
  self.assertEqual(self.runs.insights()["skills"][0]["reportedRuns"],0)
 def test_illegal_order(self):
  self.prepare()
  with self.assertRaises(RunConflict):self.event("reported_applied")
  with self.assertRaises(RunConflict):self.event("result_returned",artifactId="artifact-one")
 def test_replay_payload_conflict(self):
  self.prepare()
  with self.assertRaises(RunConflict):self.event("prepare",skillId="skl_test_review",task="Different task",client="Test client")
 def test_agent_cannot_claim_other_run(self):
  self.prepare()
  other=Principal("Other agent",frozenset({"skills.read","skills.report"}),True)
  with self.assertRaises(PermissionError):self.event("read",who=other)
 def test_restart_and_rename_preserve_identity(self):
  self.prepare();self.event("read");self.event("reported_applied")
  self.skill.rename(self.library/"renamed");self.catalog.refresh()
  reopened=SkillRuns(self.root/"runs.sqlite3",self.catalog)
  self.assertEqual(reopened.insights()["skills"][0]["reportedRuns"],1)
  self.assertEqual(reopened.listing()["runs"][0]["skillId"],"skl_test_review")
 def test_snapshot_remains_exact_after_source_changes(self):
  self.prepare();original=(self.skill/"SKILL.md").read_text()
  (self.skill/"SKILL.md").write_text("Revised instructions")
  self.assertEqual(self.event("read")["instructions"],original)
 def test_history_survives_skill_folder_rename(self):
  editor=SkillEditor(self.catalog,self.root/"state")
  doc=editor.document("skl_test_review","SKILL.md")
  editor.save({"id":"skl_test_review","file":"SKILL.md","text":doc["text"]+"\nMore detail.","sha256":doc["sha256"],"requestId":"save-one"})
  self.skill.rename(self.library/"renamed");self.catalog.refresh()
  self.assertEqual(editor.history("skl_test_review","SKILL.md")["versions"][0]["text"],doc["text"])
 def test_old_journal_is_bound_before_renaming(self):
  editor=SkillEditor(self.catalog,self.root/"state")
  doc=editor.document("skl_test_review","SKILL.md")
  editor.save({"id":"skl_test_review","file":"SKILL.md","text":doc["text"]+"\nA detail.","sha256":doc["sha256"],"requestId":"old-save"})
  with editor.connect() as db:db.execute("UPDATE edits SET object_id=NULL")
  editor=SkillEditor(self.catalog,self.root/"state")
  self.skill.rename(self.library/"renamed");self.catalog.refresh()
  self.assertEqual(editor.history("skl_test_review","SKILL.md")["versions"][0]["text"],doc["text"])
 def test_unidentified_skills_are_not_guessed(self):
  (self.skill/"workspace-skill.json").unlink();self.catalog.refresh()
  key=next(iter(self.catalog.items))
  with self.assertRaises(ValueError):self.event("prepare",skillId=key,task="Review",client="Test")
 def test_duplicate_identity_fails_closed(self):
  shutil.copytree(self.skill,self.library/"duplicate")
  with self.assertRaises(ValueError):self.catalog.refresh()
 def test_retained_skills_do_not_fill_working_library(self):
  (self.library/"skills.json").write_text(json.dumps({"skills":[{"name":"review","active":False}]}))
  self.catalog.refresh()
  self.assertEqual(self.catalog.listing()["skills"],[])
  self.assertEqual(self.catalog.document("skl_test_review")["id"],"skl_test_review")
 def test_no_automatic_read_event(self):
  self.catalog.document("skl_test_review")
  self.assertEqual(self.runs.listing()["runs"],[])

class KnowledgeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.repo=self.root/"knowledge";self.repo.mkdir()
  for args in [("init","-b","main"),("config","user.name","Demo"),("config","user.email","demo@example.com")]:
   subprocess.run(["git","-C",str(self.repo),*args],capture_output=True,check=True)
  self.library=KnowledgeLibrary(self.repo,self.root/"state")
 def tearDown(self):self.temp.cleanup()
 def test_semantic_checkpoint_and_truthful_status(self):
  self.library.stage({"prompts/review.md":"Review the product"})
  self.assertTrue(self.library.status()["savedLocally"])
  self.assertFalse(self.library.status()["committed"])
  status=self.library.checkpoint("Add a product review method")
  self.assertTrue(status["committed"]);self.assertFalse(status["backedUp"])
 def test_local_save_without_remote(self):
  self.library.stage({"standards/writing.md":"Use concrete verbs"})
  self.assertEqual((self.repo/"standards/writing.md").read_text(),"Use concrete verbs")
 def test_checkpoint_conflict_keeps_user_edit(self):
  self.library.stage({"prompts/review.md":"Original"})
  (self.repo/"prompts/review.md").write_text("Manual edit")
  result=self.library.stage({"prompts/review.md":"Changed source"})
  self.assertEqual(result["conflicts"],["prompts/review.md"])
  self.assertEqual((self.repo/"prompts/review.md").read_text(),"Manual edit")
  with self.assertRaises(ValueError):self.library.checkpoint("Revise the review method")
 def test_paths_and_binary_data_rejected(self):
  for path in ("../escape.md","state.sqlite3","/escape.md",".env"):
   with self.assertRaises(ValueError):self.library.stage({path:"content"})

if __name__=="__main__":unittest.main()
