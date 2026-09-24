# Knowledge and operational state

Authored instructions, standards, prompts and references belong in a private Git checkout. Configure knowledge_root outside the public engine. Operational state, event history, journals, indexes and caches remain in a private runtime directory outside every Git checkout. Secret references resolve only in the privileged service.

KnowledgeLibrary stages authored text without network access, detects manually edited targets, and creates semantic commits on request. A checkpoint requires a meaningful summary. It never deletes a disappeared source or silently replaces a local edit. GET /api/knowledge reports saved locally, committed and backed up separately. A commit alone never establishes remote backup.

A private instance supplies its own export/import adapter. The supplied integration boundary permits existing authoritative editors to journal locally, then checkpoint text asynchronously. Such a compatibility export is a versioned mirror, not a second editable authority. Reconcile edits before switching the canonical source. The engine never imports a private repository.

Binary assets use the artifact/object provider. Knowledge stores identities, versions, hashes and references. Credentials and live databases must never appear in commits. Database backup adapters should encrypt snapshots, keep encryption identities in an OS secret store, and restore only into a new location before any deliberate recovery.

Git availability does not affect local editing. Remote outages leave a pending backup state and retry asynchronously. A private deployment must verify its configured destination and visibility before publishing private knowledge.

No general cloud sync, remote database backup, upstream skill updater, or hosted multiuser service is implied by this interface.
