# Remote Desk Pro

Self-hosted remote access MVP built with React, FastAPI, authenticated WebSockets and a visible-consent Python host agent.

## Current scope
- Argon2 password hashing and signed JWT sessions.
- First account is admin; subsequent accounts are technicians.
- Nine-digit device IDs, one-time agent secrets and expiring six-digit passwords.
- Authenticated WebSocket signaling and binary JPEG frame relay.
- Manual local ALLOW approval is the default; an owner may explicitly enable trusted unattended access using the saved device PIN.
- SQLite WAL locally; SQLAlchemy URL support for PostgreSQL.
- React dashboard and Render Free Docker deployment files.

This is an early MVP, not a full TeamViewer replacement. Bidirectional clipboard sync and viewer-to-host file transfer are implemented with explicit host approval. Audio, multi-monitor controls, Wake-on-LAN, and a WebRTC peer-media path are not implemented. Approved sessions are locally recorded after a visible host-consent notice; a visible maintenance banner can be enabled by the viewer and has a local emergency unlock.

## Security and deployment
The host agent is interactive, visible and does not install a hidden service or auto-start. Use HTTPS/WSS and a unique APP_SECRET_KEY. Render Free storage is ephemeral, so configure managed PostgreSQL for durable accounts/devices. Public STUN alone cannot guarantee connectivity; WebSocket relay requires load testing before commercial use.


## Windows desktop host app

Run RemoteDeskPro-Agent.exe by double-clicking it. On first launch, sign in to an existing account (or create one) and the app automatically registers this computer. The app displays the nine-digit device ID and six-digit dynamic password with Copy and Rotate Password controls.

- Device identity and the agent secret are stored in %APPDATA%\RemoteDeskPro\config.json; secrets are protected with Windows DPAPI.
- Rotating logs are stored in %APPDATA%\RemoteDeskPro\agent.log.
- The password expires after 24 hours of inactivity; a successful viewer connection refreshes the idle window. It is rotated on agent restart or when the user selects Rotate Password.
- Manual approval is the default. Trusted unattended access bypasses the popup only when the owner enables it and sets a valid saved PIN. The host can disconnect at any time.
- CLI/headless mode remains available with --server, --device-id, --secret, and --dynamic-password.
- Set RDP_SERVER in the local environment or deployment dashboard; no production endpoint is embedded in tracked source.

Existing viewer connections use an authenticated WebSocket after the one-time session-token handshake. WebSocket heartbeat and client/host reconnect loops keep a live session recoverable through transient transport resets; a session ends when the host or viewer explicitly disconnects.


## Unified V2 desktop client
The V2 Windows executable launches the host console and can open the authenticated web viewer inside an embedded WebView window. Configure `RDP_SERVER` before launch. Trusted unattended access remains opt-in and requires the device's saved PIN; otherwise host approval remains active. Semantic action recording is enabled only while the privacy blank screen is active. Typed text and clipboard payloads are intentionally excluded from workflow JSON.
