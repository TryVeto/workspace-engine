# Public release

The project is licensed under Apache License 2.0. The public repository is a new history made from an explicit source allowlist, deterministic fabricated fixtures and generic machinery.

Release checks:

- Run the unit suite in normal and optimized Python.
- Run the browser harness on its isolated demo.
- Scan the working tree, staged tree, all commit trees and annotated tags with tools/release_gate.py --history.
- Apply the private deployment's additional deny policy outside this checkout.
- Read the complete public tree as an adversarial recipient: source paths, fixtures, screenshots, credentials, internal names, hostnames and operational history all count.
- Preserve third-party license notices.
- Confirm the destination before pushing.
- Clone the public result and rerun the gate and smoke checks.

The scanner is a release gate, not a guarantee that arbitrary text is safe. Known private identifiers belong in the release operator's external policy. Binary assets and screenshots are rejected by default. CI never requires private data or secrets.
