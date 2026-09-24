# Skill runs

Each active skill can carry a portable `workspace-skill.json` beside `SKILL.md`:

```json
{"id":"skl_demo_product_review","source":"local","local_changes":false}
```

The identity file travels with the package. Optional aliases preserve earlier references. Upstream imports can include source, upstream, upstream_revision, imported_at, license, imported_sha256, and based_on. The catalog compares an imported hash with the current instructions to show local changes. Missing provenance remains unknown; no automatic upstream replacement is performed. Duplicate identities need reconciliation.

A private library's optional skills.json registry can mark retained packages with active: false. They remain readable by identity but disappear from the working list. Marketplace discovery never activates a package.

## Report a run

POST /api/skill-runs with a stable requestId, runId and action:

1. prepare: skillId, task, client, optional taskId and expected revision.
2. read: returns the stored instructions and records one read.
3. reported_applied: the authenticated actor reports material application.
4. result_returned: artifactId identifies the returned result.
5. result_reviewed: outcome is accepted, revised, or rejected.

Prepare captures the package revision and exact root instructions. A run reports one skill; separate run IDs can share a task ID for several skills. Repeated reads within a run count once. Retries must preserve request ID and payload. Out-of-order reports and conflicting replays fail. External result references are reported evidence, not independently verified artifact contents.

Agents require skills.report and can report only their own runs. Review requires skills.review and a person identity; even an agent granted that capability cannot claim human acceptance. Listing requires insights.read. Ordinary catalog reads, copies, and opening a file never create a run or application event.

GET /api/insights/skills returns Skill, Reported runs, and Last used. Counts include explicit reported_applied events once per run. GET /api/skill-runs?skillId=... returns task, client, authenticated actor, revision, exact timestamps, result reference and review outcome. Activity outside these paths is unknown.

The browser offers Use in run in the skill's file actions and Use a skill in Insights. Tests use fabricated work, never private records.
