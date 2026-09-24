# Release candidate verification

The automated suite exercises revision conflicts, identical retries, restart persistence, exact skill bytes, path traversal and symlinks, explicit file roots, private runtime paths, provider capabilities, cookie/origin/CSRF protection, scoped agent reads and writes, credential exclusion, static allowlists, session expiry, approval-before-execution, and uncertain side effects after restart. The release scanner is tested against a secret deleted from an earlier commit.

The browser harness creates a fresh fabricated demo. It checks 16 surfaces, 18 desktop/mobile/dark views, number-key ownership, exact prompt copying, filtered shortcuts, typing isolation, a lost task-save response, offline workspace draft recovery, prompt creation and edit persistence, and warm navigation latency. It fails on page errors and document overflow.

The current local verification passed 40 Python tests under normal and optimized Python and all browser checks. Warm navigation p95 was approximately 2 ms on the verification host; this is a local measurement, not a universal performance promise. The workflow and capability tests use fabricated adapters and make no external side effects.

Not verified: real R2 round trips, mail/calendar/AI providers, Windows, Safari, multi-user hosting, or operation while a laptop is asleep. The macOS private instance uses a Keychain-backed scoped agent identity; this does not install an autonomous agent scheduler.

Skill-run verification covers the complete browser flow through accepted review and reload, repeated-read deduplication, exact instruction snapshots, package renames, history recovery, out-of-order reports, agent scope checks, and rejection of agent-authored human reviews. Knowledge checks cover local staging, semantic commits, truthful backup state, preserved manual edits, and file boundaries.
