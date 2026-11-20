# Remote Desk Pro — Project Manifest

**Workspace:** E:\GitHub-Vault\remote-desk-pro  
**GitHub:** https://github.com/lokeshmakhijani1-debug/remote-desk-pro (private)  
**Render blueprint:** exs-dc08of8n74is73a6eb0g  
**Planned service:** remote-desk-pro-pj29 (Free, Singapore)  
**Current status:** Source committed; Render plan awaits explicit review/approval; build verification pending.

| Component/File Path | Purpose | Installed Packages & Versions | Ports/Env Vars | Deployment Status |
|---|---|---|---|---|
| backend/main.py | REST auth, device pairing/password rotation, rate-limited login/connect, role checks, WebSocket binary relay, health/manifest | FastAPI, Uvicorn, SQLAlchemy, PyJWT, Argon2 | PORT, APP_SECRET_KEY, DATABASE_URL, MAX_CONCURRENT_SESSIONS | Source committed; tests pending |
| backend/database.py | User/device/audit models; SQLite WAL; SQLAlchemy URL abstraction | SQLAlchemy 2.x, psycopg 3.x | DATABASE_URL | Source committed |
| backend/security.py | Argon2 secret hashing, signed session tokens, ID/password generation | PyJWT, argon2-cffi | APP_SECRET_KEY | Source committed |
| backend/config.py | Typed environment configuration | pydantic-settings | .env variables | Source committed |
| frontend/src/App.tsx | Remote-control dashboard, pairing, agent secret display, password rotation, viewer and device list | React 19, lucide-react | Browser API origin | Source committed; build pending |
| frontend/src/styles.css | Responsive TeamViewer-inspired visual system | Tailwind CSS 4 | — | Source committed |
| frontend/src/api.ts | REST client and WebSocket URL helper | Browser Fetch/WebSocket | VITE_API_BASE | Source committed |
| frontend/src/vite-env.d.ts | Vite client type declarations | Vite 8 | — | Source committed |
| agent/host_agent.py | Interactive host consent, screen capture, JPEG relay and gated input | websockets, mss, Pillow, pyautogui | RDP_SERVER, RDP_DEVICE_ID, RDP_AGENT_SECRET | Source committed; runtime test pending |
| Dockerfile | Multi-stage frontend build and Python runtime | Node 24, Python 3.12 | PORT=10000 | Source committed |
| render.yaml | Free-tier Render service blueprint and health check | Render Docker runtime | APP_SECRET_KEY (generated), DATABASE_URL, STUN_URL, CORS_ORIGINS | Blueprint plan created; awaiting approval |
| requirements.txt | Backend runtime dependencies | FastAPI, Uvicorn, SQLAlchemy, PyJWT, Argon2, pydantic-settings, email-validator | — | Source committed |
| requirements-dev.txt | Automated test dependencies | pytest, httpx | — | Source committed |
| tests/test_health.py | Health and manifest API tests | pytest, FastAPI TestClient | — | Source committed; execution pending |
| .github/workflows/ci.yml | Backend test and frontend build jobs on push/PR | GitHub Actions, Python 3.12, Node 24 | — | Source committed; run not yet verified |
| .env.example | Safe local configuration template | — | Runtime settings | Source committed |
| README.md / docs/SECURITY.md | Setup, pairing, security and deployment caveats | — | — | Source committed |

## Architecture and limitations
- Current media transport is authenticated WebSocket binary JPEG relay. STUN/TURN ICE configuration is returned by the API, but a WebRTC peer-connection media path is not implemented.
- Host agent requires a visible interactive ALLOW approval for every viewer session. No hidden service or auto-start behavior.
- Local persistence: SQLite WAL. Render Free has ephemeral storage; use managed PostgreSQL for durable production state.
- Maximum concurrent viewer sockets is configured to 50, but not load-tested or certified.
- Login and connection attempts have in-memory IP-based throttling; distributed rate limiting is not implemented.
- File transfer, clipboard, chat delivery, audio, recording, multi-monitor switching, WOL, unattended access and user-invitation administration are not implemented.
- No paid Render plan or external paid TURN service is part of the plan.

## Phase checkpoints
| Phase | Status | Evidence |
|---|---|---|
| 1 — Audit & permissions | Complete | User approved all permissions and selected RustDesk/noVNC-inspired reverse-engineered design |
| 2 — Backend & signaling | Source committed; verification pending | Auth, pairing, password rotation, WebSocket relay |
| 3 — Frontend | Source committed; build pending | React dashboard, credentials, viewer canvas |
| 4 — Host agent | Source committed; runtime test pending | Visible host consent, frame capture, explicit input gate |
| 5 — GitHub & Render | GitHub repo created and source committed; Render plan awaits review | Private repo, Free Singapore service, Dockerfile, /api/health check, auto-deploy from main |

## Known blockers / next verification
- Complete local dependency installation and run npm build, backend tests and host-agent import checks.
- Verify Docker image build and local HTTP/WebSocket integration.
- Approve the reviewed Render Blueprint sync before the service can be created.
- SQLite on Render Free is ephemeral; durable production use requires a managed PostgreSQL DATABASE_URL.
- WebSocket JPEG relay is not a replacement for WebRTC media; 50 concurrent sessions require load testing and likely a dedicated relay service.


## Deployment update — 2026-11-20
- Render Blueprint sync approved by user and applied: `exe-dc08pck9v7es73avpi0g`.
- Render service: `remote-desk-pro-pj29`; service ID: `srv-dc0917utlv9c739h7o30`.
- Deployment: `dep-dc0918etlv9c739h7p80`; status: **live**; Docker build and deploy events both succeeded.
- Plan/region: **Free / Singapore**; auto-deploy from `main`; configured health check path: `/api/health`.
- Public application: https://remote-desk-pro-pj29.onrender.com — fetched successfully; title `Remote Desk Pro`; sign-in/create-account landing screen rendered.
- Health endpoint: https://remote-desk-pro-pj29.onrender.com/api/health — fetched successfully; body reports `status: ok`, service `remote-desk-pro`, version `0.1.0`, database `configured`, capacity target `50`.
- Manifest endpoint: https://remote-desk-pro-pj29.onrender.com/api/manifest — fetched successfully; reports WebSocket binary relay and device pairing enabled; file transfer, clipboard sync and recording disabled.
- Verification scope: public page + health + manifest HTTP fetch only. No account creation/login, host-agent pairing, remote-control session, WebSocket frame relay, load test or security penetration test performed.
- Important operational risk remains: Render Free filesystem is ephemeral and the current SQLite database is not backed by persistent disk. Do not rely on account/device data surviving service replacement/redeploy; configure managed PostgreSQL before real users or production data.
- Browser Use interactive automation was unavailable due insufficient credits; direct public endpoint fetches were used instead.
