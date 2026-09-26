# Workspace task pages

This optional Electron shell keeps the Workspace engine as the product and adds a bounded Chromium task-page pane beside it.

It deliberately is not a general browser. It provides persistent page login state, tabs, navigation, page context/screenshot capture, and explicit computer-control primitives. It does not implement password management, extension compatibility, browser sync, browser profiles, ad blocking, or a consumer history product.

Run: npm install, then WORKSPACE_URL=http://127.0.0.1:18999 npm start.

Third-party pages use Electron's persistent persist:workspace-web partition with Node integration off, context isolation and sandboxing on, and browser permission requests denied by default. The Workspace renderer may control the page pane only from the configured local Works origin.
