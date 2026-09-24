# Security boundary

This release is a single-user loopback app, not a remotely accessible multi-user server. It binds only to 127.0.0.1. Local processes running as the same OS user remain inside the trust boundary. Do not expose it through a tunnel or a public reverse proxy without adding authenticated transport and an appropriate multi-user permission model.

HTTP requests require an allowed Host. Browser writes require an exact matching Origin, an HttpOnly SameSite=Strict session cookie, and a constant-time CSRF check. Browser sessions expire. Scoped bearer credentials are accepted only for non-browser agent requests. Catalog and search results respect the principal's record capabilities. Static files come from an explicit asset manifest. The browser receives neither provider credentials nor the private configuration.

File operations require explicit roots and reject escaping paths and symlinks. Source file previews are inert text. Credentials use `keychain:account` or `env:NAME` references. On macOS, `tools/secret.py account --generate` stores a credential directly in the Keychain without printing it. Environment references are for a process or managed secret injection, not committed .env files. Optional R2 credentials also accept accessKeyRef and secretKeyRef.

Runtime directory permissions are private; databases use synchronous durable commits. This is not at-rest encryption. Use OS disk encryption and appropriate account protection. Browser draft storage is also private data and is not a substitute for a backup.

The release gate scans filenames, binary types, credential signatures, credential-like assignments, home paths, non-fixture emails, URL hosts, and all reachable Git commits and blobs. A private denylist can be set through `git config workspace.releasePolicy /path/to/private-policy.json`. That file stays outside this repository. Automated scanning is a guardrail, not proof that arbitrary text is non-sensitive. Review new fixtures and assets before publication.

References: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html and https://docs.github.com/en/actions/reference/security/secure-use
