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


## Phase 6 — database isolation implementation
- Database URLs beginning with `postgres://` or `postgresql://` are normalized to SQLAlchemy's installed Psycopg 3 driver (`postgresql+psycopg://`). SQLite remains supported.
- All application models use dedicated `rdp_*` table names: `rdp_users`, `rdp_devices`, and `rdp_audit_events`; the device foreign key points only to `rdp_users.id`.
- Startup verifies a real `SELECT 1` connection before creating only the application's prefixed tables. No schema-wide migrations, table drops, or writes to unprefixed/public application tables are performed.
- `/api/health` now reports the verified dialect (`sqlite` or `postgresql`) and returns HTTP 503 when the database cannot be reached.
- PostgreSQL connection compatibility is implemented in source; live Supabase connectivity is pending the user's secure addition of `DATABASE_URL` in the Render service environment. Do not put credentials in GitHub, logs, chat, or this manifest.

## Phase 6.2 — relay feature implementation
- Added authenticated clipboard relay events (`clipboard_update`) in both directions, gated on explicit host approval and limited to 64 KiB per text update. Audit entries record character counts only; clipboard contents are not written to audit logs.
- Added chunked viewer-to-host file transfer: host must approve the session and choose a local save destination; transfers are limited to 50 MiB total and 192 KiB per decoded chunk. Filenames are reduced to a safe basename. The host agent confirms completion only after the expected byte count is received.
- Added viewer UI for clipboard send/receive and file upload; added Windows host-agent clipboard monitoring and host-side file-save dialog.
- File transfer is currently one-way (viewer to host). Host-to-viewer transfer, resumable transfers, checksum verification, and antivirus scanning are not implemented.
- Unattended access remains disabled; the host agent asks for visible approval for every session.
- Render commit `1fbd1adf01dcdddf3ea6be6f9f795d54ea0955c7` built successfully and deployed live. Live HTTP health returned `database: sqlite`; the new clipboard/file handlers have not yet been exercised end-to-end.

## Phase 6 current checkpoint — 2026-11-20
- Latest deployed source commit: `d10bdb32ce9d8ca778e97ffd6bd2358e95e365e7`; Render deployment `dep-dc098hrbc2fs73aplpq0` is **live**.
- Live HTTP health verified: `status=ok`, `database=sqlite`. The application is still using its existing SQLite fallback; Supabase PostgreSQL has not yet been connected.
- Live manifest now advertises `clipboard_sync=true` and `file_transfer=true`; these flags mean handlers are present, not that the end-to-end data paths have passed a live test.
- PostgreSQL driver compatibility is implemented using Psycopg 3 URL normalization. All ORM tables are prefixed `rdp_`; existing unprefixed tables are not migrated, dropped, or queried.
- Relay protocol: host/viewer WebSocket authentication; host approval gate; bidirectional clipboard updates with a 64 KiB text limit; viewer-to-host chunked file transfer up to 50 MiB, with a host-side save dialog and per-chunk validation. File transfer is one-way only at this checkpoint.
- Security limits: clipboard content is not stored in audit logs (only character counts); file transfer names are reduced to a basename; unattended access remains unavailable; each viewer session requires visible host approval.
- Verification completed: Docker/frontend build succeeded for commit `1fbd1adf01dcdddf3ea6be6f9f795d54ea0955c7`; latest deployment is live and both public HTTP endpoints returned successfully. Earlier intermediate builds failed because the first frontend patch wrote literal escaped newline characters; corrected in `1fbd1ad`.
- Not yet verified: Supabase connection; live WebSocket binary frame relay; clipboard sync; file transfer; audit event assertions; PyInstaller packaging; running the standalone agent on the connected Windows device. Desktop Commander calls to the connected device have remained pending and one timed out without a result.
- Agent build script: `agent/build_windows.ps1`; intended output is `agent/dist/RemoteDeskPro-Agent.exe` after a successful Windows build. No executable has been produced or verified yet.
- Required next action: add `DATABASE_URL` directly in the Render service Environment page (do not send it in chat or commit it). Use the Supabase **Session pooler** URI and keep its password URL-encoded. After Render redeploys, verify `/api/health` reports `database=postgresql` before running E2E tests.
- Render service: `srv-dc0917utlv9c739h7o30`; environment changes should be made only on this service. Do not replace its existing environment variables.
