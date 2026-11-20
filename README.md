# Remote Desk Pro

Self-hosted remote access MVP built with React, FastAPI, authenticated WebSockets and a visible-consent Python host agent.

## Current scope
- Argon2 password hashing and signed JWT sessions.
- First account is admin; subsequent accounts are technicians.
- Nine-digit device IDs, one-time agent secrets and expiring six-digit passwords.
- Authenticated WebSocket signaling and binary JPEG frame relay.
- Host agent requires explicit local ALLOW approval before screen capture and remote input.
- SQLite WAL locally; SQLAlchemy URL support for PostgreSQL.
- React dashboard and Render Free Docker deployment files.

This is an early MVP, not a full TeamViewer replacement. File transfer, clipboard, audio, session recording, unattended access, multi-monitor controls, Wake-on-LAN and a WebRTC peer-media path are not implemented yet.

## Security and deployment
The host agent is interactive, visible and does not install a hidden service or auto-start. Use HTTPS/WSS and a unique APP_SECRET_KEY. Render Free storage is ephemeral, so configure managed PostgreSQL for durable accounts/devices. Public STUN alone cannot guarantee connectivity; WebSocket relay requires load testing before commercial use.
