# Security Notes

- The host agent requires an interactive terminal and explicit ALLOW approval for every viewer session.
- No hidden startup service, persistence mechanism, or stealth operation is installed.
- The agent secret is a high-entropy pairing credential; protect it like a password.
- Dynamic connection passwords expire and can be rotated by the device owner.
- Use HTTPS/WSS and a unique high-entropy APP_SECRET_KEY in production.
- Use managed PostgreSQL for persistent production data; Render Free filesystem storage is ephemeral.
- Before commercial release: add invite-only user provisioning, device revocation, distributed rate limits, audit retention, secure file scanning, clipboard/file/audio permission controls, recording consent and independent penetration testing.
- Public STUN does not relay media. WebSocket relay is bandwidth- and memory-intensive and needs load testing before concurrency is increased.
