# Workspace

A keyboard-first headquarters for work, decisions, files, prompts, and skills.

## Run the demo

macOS or Linux, Python 3.11+, and a current browser are sufficient. The local engine has no third-party Python or frontend runtime dependencies.

```sh
python3 server.py --demo
```

Open http://127.0.0.1:8988. The fabricated Northstar Studio workspace includes prompts, a skill, tasks, a decision, an update, files, reference documents, and a canvas. No personal libraries or directories are discovered. The first run copies deterministic fixtures into a separate writable runtime; later runs preserve edits. Use a new `--data` directory to start another demo.

## Private instance

Create a directory beside this checkout, then copy `examples/instance.example.json` into its `config/instance.json`. Set a runtime directory outside every Git working tree. Start with:

```sh
python3 server.py --config ../workspace-private/config/instance.json
```

The engine knows schemas. Your instance owns configuration, source documents, skills, integrations, and identities. Runtime stores and credentials belong outside both repositories. See [architecture](docs/ARCHITECTURE.md), [security](docs/SECURITY.md), and [agent API](docs/AGENTS.md).

## Keyboard

Option/Alt + 1–9 switches primary sections. Unmodified numbers belong to the current surface: in Prompts, they copy a prompt. Command/Control K opens search; / focuses section search; arrows select; Enter opens; Escape returns. Typing fields and dialogs own their keys. ? opens the shortcut reference.

## Check a change

```sh
python3 -m unittest discover -s tests -v
python3 -O -m unittest discover -s tests -q
python3 tools/release_gate.py --history
git config core.hooksPath .githooks
```

The browser harness is `tests/browser.mjs`; it requires Playwright supplied by the developer and a disposable demo server. It never targets a private instance by default.

## Skill runs and knowledge

Insights records a complete, explicit skill run: prepare, read, report application, return a result, and human review. File access alone never counts as application. Skill identities survive folder renames; instructions and package revisions are captured for each run. See [skill runs](docs/SKILL-RUNS.md).

Authored knowledge can use a separate private Git checkout. Local saves and recovery journals do not wait for a commit or network. Semantic checkpoints preserve manually edited files as conflicts rather than overwriting them. Operational databases stay outside Git. See [knowledge](docs/KNOWLEDGE.md).

## License

Apache License 2.0. See [LICENSE](LICENSE). Retained third-party notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

This release includes local storage and concrete files, tasks, skills, and search providers. Mail, calendar, AI, and remote synchronization are extension interfaces, not connected services. A private compatibility host can consume the shared engine while its remaining integrations migrate.
