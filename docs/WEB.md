# Web-native work

Workspace treats web pages as evidence attached to work, not as a replacement browser.

## Surfaces

- **Web** is the library of explicitly captured pages.
- **Browser extension** sends the active page, selected text, readable page text, visible screenshot, and current-window tab metadata only after the user clicks Send or invokes the extension shortcut.
- **Native messaging host** is a capture-only identity. It can create Web artifacts but cannot read them back.
- **Desktop task pages** are optional. Electron embeds third-party pages beside Workspace using WebContentsView and a named persistent session.

A Web artifact can be attached to an existing Work record through the same source relationship used by files, prompts, and other evidence. The work object remains the organizing primitive.

## Deliberate limits

V1 does not implement password management, Chrome Web Store compatibility, bookmark or history sync, browser profiles, ad blocking, consumer browser history, DRM/media compatibility work, or browser account sync.

The embedded page surface denies browser permission requests by default and keeps Node integration disabled, context isolation enabled, and renderer sandboxing enabled.

## Browser bridge install

On macOS:

    python3 tools/browser_bridge/install.py --brand "My Workspace" --workspace-url http://127.0.0.1:18999

The installer creates a private branded copy of the extension under Application Support, stores a random bridge credential in Keychain, and registers the native messaging host for Chrome, Chrome for Testing, Chromium, and Dia. Load the printed extension directory as an unpacked extension in the browser you want to use.

The committed extension stays generic. Private instances may brand the generated copy without changing its deterministic extension id.

## Desktop task pages

From apps/desktop-web:

    npm install
    WORKSPACE_URL=http://127.0.0.1:8988 npm start

The desktop bridge exposes only tab/navigation state, page context, screenshot capture, and bounded coordinate-level click/type/scroll/key primitives to the trusted Workspace renderer.
