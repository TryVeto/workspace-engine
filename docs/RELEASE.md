# Public release checklist

1. Start from a new Git repository. Never attach the private application's Git history.
2. Review every added file. Demo content must be invented, including fixtures, titles, and screenshots. The initial release deliberately excludes raster screenshots, archives, databases, caches, and exports.
3. Run the working-tree and full-history release gate, including the local private policy. Run the same tests under normal and optimized Python.
4. Run the browser harness against a new disposable demo. Verify keyboard ownership, exact copying, local navigation, failed-save recovery, narrow panes, and dark mode.
5. Clone the candidate into an empty directory and run the demo with a new runtime directory. It must not need the private instance or a credential.
6. Examine what a stranger can learn from every commit, author field, fixture, source string, and retained attribution. Secret scanners do not replace this review.
7. Select the project license and public destination. The pre-push hook refuses publication without LICENSE. Retain all required third-party notices.

CI is read-only, uses a full-history checkout pinned to a verified commit, and runs without private credentials. Do not use pull_request_target to execute fork code.

The local release policy is a private JSON file containing denyPatterns. Do not publish customer names in the scanner intended to protect them. Git stores deleted files: a failing historic blob requires a clean extraction or deliberate history remediation, never merely a new deletion commit.
