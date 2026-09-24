# Connect an agent

The service is local. A remote agent needs an explicitly authorized local bridge; the application is not internet-accessible.

Configure a distinct identity in the private instance:

```json
{
  "agents": {
    "Review agent": {
      "secretRef": "keychain:workspace-review-agent",
      "capabilities": ["workspace.read", "tasks.read", "prompts.read", "skills.read", "decisions.read", "decisions.request", "updates.read", "updates.write", "search.read"]
    }
  }
}
```

Create its secret with `python3 tools/secret.py workspace-review-agent --generate`, restart the instance, and use `tools/agent.py --config ../workspace-private/config/instance.json --agent 'Review agent' /api/hq`. The CLI retrieves the credential server-side; it is never passed in a command argument. Raw HTTP clients send Authorization: Bearer with the resolved credential. Do not use the browser CSRF value as an agent credential.

Read routes include `/api/state`, `/api/catalog`, `/api/search?q=review`, `/api/hq`, and `/api/health`. File and export endpoints require separate capabilities. `/api/providers` describes registered operations and requires providers.inspect.

POST `/api/hq` to return an update:

```json
{
  "requestId": "review-result-001",
  "action": "update.create",
  "record": {
    "title": "Prototype review complete",
    "body": "The fabricated prototype has three reproducible findings.",
    "checks": "Keyboard review of the demo flow.",
    "nextAction": "Choose the first correction.",
    "status": "returned"
  }
}
```

Use decision.create with title, body, recommendation, and two to six options to request a decision. Resolving a decision requires decisions.resolve, which agents do not receive by default. The server stamps the authenticated actor and ignores caller-supplied attribution.

Reuse the same requestId and payload after a lost response. A changed payload needs a new identity. An HTTP 409 means the observed revision is stale; retrieve the record and reconcile the draft. Never convert a conflict into an unconditional overwrite. An update reports what happened; it does not establish approval. Copying a brief does not execute it.
