# Boundaries

The public engine contains reusable UI, commands, Canvas, source adapters, schemas, local search, workflow machinery, and invented fixtures. It imports no private repository and starts no personal discovery process.

A private instance supplies explicit configuration. It can keep versioned private prompts, skills, or custom integration code. SQLite stores, indexes, connector caches, snapshots, and exports stay outside Git. Credentials are referenced through Keychain or the host secret environment; they are never serialized into instance.js or API exports.

The browser holds display data, selection, local drafts, and a short-lived CSRF value. The HTTP service owns filesystem access, SQLite, connector credentials, and capability checks. UI responses and local navigation do not wait for remote providers. Search uses local FTS with content hashes; only changed documents are reindexed.

## Code map

- `apps/web`: shell and surfaces.
- `packages/ui`: shared visual grammar and controls.
- `packages/commands`: section ownership and typing guards.
- `packages/canvas`: page and spatial canvas interactions.
- `packages/schemas`: transport types.
- `packages/engine/workspace_engine`: local storage, search, providers, authorization, workflows, and HTTP adapter.
- `examples/demo-workspace`: authored fake source records, never anonymized production data.

Provider protocols cover files, tasks, messages, calendar, search, AI streaming, and storage. Local files, tasks, skills, and search have concrete adapters. Mail, calendar, and AI providers are extension contracts; no provider is connected by default. R2 is optional and remains unverified until a real object read/write/hash check succeeds.

Custom private launchers can import Workspace, register adapters with explicit operation-to-capability mappings, and supply an app_factory to make_server. Keep integration credentials and custom adapters in the private instance. Registration never grants a principal a capability.

## Writes

Workspace, tasks, culture, prompts, decisions, updates, and skill edits use observed revisions and stable request identities. SQLite writes are transactional; stale saves return 409. The browser saves workspace drafts locally before sending and retains failed drafts for export. Skill edits retain per-document drafts and before-images. Files use observed roots, content hashes, immutable versions, and revision-checked moves.

`Workflows` is a reusable side-effect journal. A draft must be explicitly approved by a person before execution. An adapter must return a confirmed receipt. A timeout becomes indeterminate, and automatic retries are blocked across restarts. A process that dies during execution also requires reconciliation. Decision cards themselves never send messages or execute external actions.

There is no cloud sync service, native desktop binary, installed mail/calendar integration, or autonomous agent scheduler in this release. The engine supports those extensions without pretending they are connected.
