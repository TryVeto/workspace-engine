# Workspace Web extension

Manifest V3 extension for explicitly sending the active page to Workspace.

The extension uses activeTab, so page content is not available until the user invokes the extension. A service worker gathers the requested page context and sends it to the registered native messaging host. Web pages cannot message the native host directly.

Install the native host with python3 tools/browser_bridge/install.py. The installer prints the private extension directory to load unpacked.
