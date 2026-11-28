# Remote Desk Pro â€” Project Manifest

**Workspace:** E:\GitHub-Vault\remote-desk-pro  
**GitHub:** https://github.com/lokeshmakhijani1-debug/remote-desk-pro (public)  
**Render blueprint:** exs-dc08of8n74is73a6eb0g  
**Render service:** remote-desk-pro-pj29 (Free, Singapore)  
**Current status:** Phase 6.1â€“6.4 live verification passed on 2026-11-21; PostgreSQL, relay E2E, Windows EXE, and cloud pairing verified.

| Component/File Path | Purpose | Installed Packages & Versions | Ports/Env Vars | Deployment Status |
|---|---|---|---|---|
| backend/main.py | REST auth, device pairing/password rotation, rate-limited login/connect, role checks, WebSocket binary relay, health/manifest | FastAPI, Uvicorn, SQLAlchemy, PyJWT, Argon2 | PORT, APP_SECRET_KEY, DATABASE_URL, MAX_CONCURRENT_SESSIONS | Source committed; tests pending |
| backend/database.py | User/device/audit models; SQLite WAL; SQLAlchemy URL abstraction | SQLAlchemy 2.x, psycopg 3.x | DATABASE_URL | Source committed |
| backend/security.py | Argon2 secret hashing, signed session tokens, ID/password generation | PyJWT, argon2-cffi | APP_SECRET_KEY | Source committed |
| backend/config.py | Typed environment configuration | pydantic-settings | .env variables | Source committed |
| frontend/src/App.tsx | Remote-control dashboard, pairing, agent secret display, password rotation, viewer and device list | React 19, lucide-react | Browser API origin | Source committed; build pending |
| frontend/src/styles.css | Responsive TeamViewer-inspired visual system | Tailwind CSS 4 | â€” | Source committed |
| frontend/src/api.ts | REST client and WebSocket URL helper | Browser Fetch/WebSocket | VITE_API_BASE | Source committed |
| frontend/src/vite-env.d.ts | Vite client type declarations | Vite 8 | â€” | Source committed |
| agent/host_agent.py | Interactive host consent, screen capture, JPEG relay and gated input | websockets, mss, Pillow, pyautogui | RDP_SERVER, RDP_DEVICE_ID, RDP_AGENT_SECRET | Packaged and live online smoke-tested |
| Dockerfile | Multi-stage frontend build and Python runtime | Node 24, Python 3.12 | PORT=10000 | Source committed |
| render.yaml | Free-tier Render service blueprint and health check | Render Docker runtime | APP_SECRET_KEY (generated), DATABASE_URL, STUN_URL, CORS_ORIGINS | Blueprint plan created; awaiting approval |
| Render V2 staging (`srv-dc42jh49v7es73dmas70`) | Dedicated Docker web service, Free Singapore, tracks `feature/v2-bidirectional-automation`; public URL `https://remote-desk-pro-rtij.onrender.com`; deployed commit `a19a14e14b434a2b3fbaf739c5d172307d988fda`; `/api/health` and `/api/manifest` verified HTTP 200 | Docker, port 10000; PostgreSQL confirmed by live health response; secret values not copied into GitHub | Live; Render-side health-check path setting is currently blank and could not be changed through the available Render service controls |
| requirements.txt | Backend runtime dependencies | FastAPI, Uvicorn, SQLAlchemy, PyJWT, Argon2, pydantic-settings, email-validator | â€” | Source committed |
| requirements-dev.txt | Automated test dependencies | pytest, httpx, websockets | â€” | Live E2E harness added
| tests/test_health.py and tests/e2e_live_relay.py | API tests and synthetic live WebSocket relay verification | pytest, httpx, websockets | â€” | Live E2E passed |
| .github/workflows/ci.yml | Backend test and frontend build jobs on push/PR | GitHub Actions, Python 3.12, Node 24 | â€” | Source committed; run not yet verified |
| .env.example | Safe local configuration template | â€” | Runtime settings | Source committed |
| README.md / docs/SECURITY.md | Setup, pairing, security and deployment caveats | â€” | â€” | Source committed |

## Architecture and limitations
- Current media transport is authenticated WebSocket binary JPEG relay. STUN/TURN ICE configuration is returned by the API, but a WebRTC peer-connection media path is not implemented.
- Host agent requires a visible interactive ALLOW approval for every viewer session. No hidden service or auto-start behavior.
- Local development supports SQLite WAL; the deployed Render service uses Supabase-managed PostgreSQL, confirmed by a live `SELECT 1` health check.
- Maximum concurrent viewer sockets is configured to 50, but not load-tested or certified.
- Login and connection attempts have in-memory IP-based throttling; distributed rate limiting is not implemented.
- Clipboard sync is bidirectional after host approval (64 KiB cap). V1 viewer-to-host transfer remains supported; V2 adds host-to-viewer SHA-256-verified chunked transfer with resume offsets and viewer acceptance (50 MiB cap); chat delivery, audio, recording, multi-monitor switching, WOL, unattended access and user-invitation administration are not implemented.
- No paid Render plan or external paid TURN service is part of the plan.

## Phase checkpoints
| Phase | Status | Evidence |
|---|---|---|
| 1 â€” Audit & permissions | Complete | User approved all permissions and selected RustDesk/noVNC-inspired reverse-engineered design |
| 2 â€” Backend & signaling | Source committed; verification pending | Auth, pairing, password rotation, WebSocket relay |
| 3 â€” Frontend | Source committed; build pending | React dashboard, credentials, viewer canvas |
| 4 â€” Host agent | Source committed; runtime test pending | Visible host consent, frame capture, explicit input gate |
| 5 â€” GitHub & Render | Deployed and live | Private repo, Free Singapore service, Dockerfile, `/api/health`, auto-deploy from main |

## Remaining production hardening
- WebSocket JPEG relay is not a WebRTC peer-to-peer media path; 50 concurrent sessions are a configured target, not a load-tested capacity guarantee.
- File transfer has no checksum verification, resume support, antivirus scan, or host-to-viewer direction.
- No penetration test, multi-user load test, or full remote input/UI interaction test has been performed.
- The local EXE is a build artifact and is intentionally not committed to GitHub; its verified path and SHA-256 are recorded below.


## Deployment update â€” 2026-11-20
- Render Blueprint sync approved by user and applied: `exe-dc08pck9v7es73avpi0g`.
- Render service: `remote-desk-pro-pj29`; service ID: `srv-dc0917utlv9c739h7o30`.
- Deployment: `dep-dc0918etlv9c739h7p80`; status: **live**; Docker build and deploy events both succeeded.
- Plan/region: **Free / Singapore**; auto-deploy from `main`; configured health check path: `/api/health`.
- Public application: RDP_SERVER â€” fetched successfully; title `Remote Desk Pro`; sign-in/create-account landing screen rendered.
- Health endpoint: RDP_SERVER/api/health â€” fetched successfully; body reports `status: ok`, service `remote-desk-pro`, version `0.1.0`, database `configured`, capacity target `50`.
- Manifest endpoint: RDP_SERVER/api/manifest â€” fetched successfully; reports WebSocket binary relay and device pairing enabled; file transfer, clipboard sync and recording disabled.
- Verification scope: public page + health + manifest HTTP fetch only. No account creation/login, host-agent pairing, remote-control session, WebSocket frame relay, load test or security penetration test performed.
- Important operational risk remains: Render Free filesystem is ephemeral and the current SQLite database is not backed by persistent disk. Do not rely on account/device data surviving service replacement/redeploy; configure managed PostgreSQL before real users or production data.
- Browser Use interactive automation was unavailable due insufficient credits; direct public endpoint fetches were used instead.


## Phase 6 â€” database isolation implementation
- Database URLs beginning with `postgres://` or `postgresql://` are normalized to SQLAlchemy's installed Psycopg 3 driver (`postgresql+psycopg://`). SQLite remains supported.
- All application models use dedicated `rdp_*` table names: `rdp_users`, `rdp_devices`, and `rdp_audit_events`; the device foreign key points only to `rdp_users.id`.
- Startup verifies a real `SELECT 1` connection before creating only the application's prefixed tables. No schema-wide migrations, table drops, or writes to unprefixed/public application tables are performed.
- `/api/health` now reports the verified dialect (`sqlite` or `postgresql`) and returns HTTP 503 when the database cannot be reached.
- PostgreSQL connection compatibility is implemented in source; live Supabase connectivity is pending the user's secure addition of `DATABASE_URL` in the Render service environment. Do not put credentials in GitHub, logs, chat, or this manifest.

## Phase 6.2 â€” relay feature implementation
- Added authenticated clipboard relay events (`clipboard_update`) in both directions, gated on explicit host approval and limited to 64 KiB per text update. Audit entries record character counts only; clipboard contents are not written to audit logs.
- Added chunked viewer-to-host file transfer: host must approve the session and choose a local save destination; transfers are limited to 50 MiB total and 192 KiB per decoded chunk. Filenames are reduced to a safe basename. The host agent confirms completion only after the expected byte count is received.
- Added viewer UI for clipboard send/receive and file upload; added Windows host-agent clipboard monitoring and host-side file-save dialog.
- File transfer is currently one-way (viewer to host). Host-to-viewer transfer, resumable transfers, checksum verification, and antivirus scanning are not implemented.
- Unattended access remains disabled; the host agent asks for visible approval for every session.
- Render commit `1fbd1adf01dcdddf3ea6be6f9f795d54ea0955c7` built successfully and deployed live. Live HTTP health returned `database: sqlite`; the new clipboard/file handlers have not yet been exercised end-to-end.

## Phase 6 current checkpoint â€” 2026-11-20
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

## Phase 6.1 Supabase credential validation checkpoint â€” 2026-11-21
- User confirmed updating Render `DATABASE_URL` with a Supabase Session Pooler URI.
- The environment-triggered deployment `dep-dc09nnbncjis73874230` failed application startup. Render app logs show PostgreSQL authentication rejected the supplied connection identity: `FATAL: password authentication failed for user "postgres"`. The health and manifest endpoints returned HTTP 503 at verification time.
- This is an authentication/configuration failure, not evidence of SQLAlchemy/Psycopg driver incompatibility. Do not run migrations or E2E tests until a successful DB connection is verified.
- The logs show the configured pooler host is in Supabase's `ap-northeast-1` region and port 5432. Supabase Session Pooler connection strings commonly require the pooler username form `postgres.<project-ref>` rather than plain `postgres`; confirm the exact username shown in Supabase's Connection string UI. Also verify the database password is current and URL-encode reserved characters (`@`, `:`, `/`, `#`, `?`, `%`) before saving it in Render. Do not send the URI or password in chat.
- Current Render service is unhealthy due to PostgreSQL authentication failure; the previous SQLite deployment was deactivated. Restore service by correcting the existing `DATABASE_URL` in Render, then verify `/api/health` returns `database=postgresql`.
- Desktop Commander device `[redacted-host-name]` (ID `c895725a-c3f5-496f-9d75-9b751772e22c`) is currently offline (last seen 30 minutes ago). Step 6.3/6.4 cannot be executed until the laptop agent reconnects.
- Live WebSocket, clipboard, file-transfer, audit, PyInstaller, and local-to-cloud smoke tests remain **not run**. Do not treat feature flags or deployment status as E2E verification.


## Phase 6 final verification â€” 2026-11-21 (IST)
This final checkpoint supersedes the earlier Phase 6 pending/blocked notes above.

### 6.1 â€” PostgreSQL health and URL normalization
- Commit: `d6a4c3b55ccf09f657ec2b5e88165621bb717e09`; Render deployment: `dep-dc09rdivcj2c73dka2s0` (**live**).
- `backend/database.py` now calls `url.strip()` before SQLAlchemy parses or normalizes the environment URL, removing trailing CR, LF, tabs, spaces, and other surrounding whitespace.
- Verified from the connected Windows laptop against `RDP_SERVER/api/health`: HTTP 200, `status=ok`, `database=postgresql`.
- No database password or connection URI is stored in this repository or this manifest.

### 6.2 â€” Live WebSocket relay, clipboard, file transfer, and audit verification
- Added `tests/e2e_live_relay.py`; added `websockets>=13,<16` to `requirements-dev.txt`.
- First live E2E run: synthetic admin account `[redacted-test-account]`, device `[redacted-device-id]`. Passed PostgreSQL health, account/device registration, host online presence, 35-byte binary frame relay, bidirectional clipboard, file offer/accept/chunk/complete (4,440 bytes), path basename sanitization, and persistent audit retrieval.
- Audit API confirmed `rdp_audit_events` contained `device.paired`, `session.requested`, `session.host_approved`, `clipboard.relayed`, `file.offered`, and `file.received` for the synthetic device.
- Second live E2E run: synthetic technician account `[redacted-test-account]`, device `[redacted-device-id]`. Passed PostgreSQL health, registration, online presence, 35-byte binary frame relay, bidirectional clipboard, safe filename handling, and multi-chunk file transfer of 185,000 bytes across 4 chunks. Audit retrieval was not repeated in this second run because the synthetic user was a technician; audit persistence had already passed in the first admin run.
- These are synthetic protocol tests, not a full visual desktop-interaction or 50-user load test.
- Synthetic test accounts/devices remain in the application database as test artifacts: admin E2E account `[redacted-test-account]` / device `[redacted-device-id]`; multi-chunk E2E technician `[redacted-test-account]` / device `[redacted-device-id]`; pre-final-deploy host pairing `[redacted-test-account]` / device `[redacted-device-id]`; final live host pairing `[redacted-test-account]` / device `[redacted-device-id]`. The first account received the initial admin role because it was the first account in the dedicated app tables; its generated password was not retained. No account/device deletion was attempted because the app currently has no safe self-service cleanup endpoint and destructive DB cleanup was not authorized.

### 6.3 â€” Standalone Windows agent build
- Build completed on `[redacted-host-name]` using Python 3.14.0 and PyInstaller 6.22.3.
- Verified executable: `E:\\GitHub-Vault\\remote-desk-pro-main\\agent\\dist\\RemoteDeskPro-Agent.exe`.
- Size: 21,302,595 bytes; SHA-256: `27AC654E1750BE03603F40D93ECEE094A53D523039837E1CD0E6A38559856AF9`.
- Standalone `--help` startup/import check passed. EXE/build intermediates and local pairing credentials are excluded from Git; no secrets are committed.

### 6.4 â€” Local-to-cloud pairing smoke test
- Launched the built EXE on `[redacted-host-name]`; Render authenticated `GET /api/devices` confirmed the host online.
- Final post-deploy smoke-test device: `[redacted-device-id]`; account: `[redacted-test-account]`; host process PID at launch: `10692`.
- After the final Render auto-deploy completed, the EXE was relaunched and authenticated `GET /api/devices` again confirmed the host online. Host process remains running and connected. Visible per-session consent remains enabled; unattended access is disabled; no viewer session was started during this pairing check.
- The EXE remains local at the path above and is not uploaded to GitHub.

### Verification boundaries
- Confirmed: PostgreSQL connection; URL whitespace normalization; host/viewer WebSocket authentication; online state; binary frame relay; bidirectional clipboard; multi-chunk viewer-to-host file relay; safe basename handling; audit persistence; Windows EXE build; local-to-cloud host pairing.
- Not certified: WebRTC peer-to-peer media (not implemented), file checksum/resume/AV scanning, host-to-viewer file transfer, unattended access, full remote-control UX, audio/recording, penetration testing, and concurrent-load capacity.

## Windows build refresh â€” 2026-11-21 (IST)
- Source branch: `main`; fetched and fast-forward pulled from `origin/main` (already up to date).
- Source commit: `24a56af636c0a27040b8a2e03f58ca3efd2baa4c`.
- Build host: `[redacted-host-name]` (Windows 10 build 19045); Python `3.14.0`; PyInstaller `6.22.3`.
- Build command: `python -m PyInstaller --noconfirm --clean --onefile --windowed --name RemoteDeskPro-Agent --collect-all mss --collect-all pyautogui --collect-all pyperclip --hidden-import tkinter --hidden-import websockets --distpath dist --workpath build host_agent.py` (run from `agent/`).
- Build result: **successful**. EXE: `E:\GitHub-Vault\remote-desk-pro-main\agent\dist\RemoteDeskPro-Agent.exe`.
- EXE size: `21299813` bytes; SHA-256: `F324BF88C2B6622058E5A21683F46E203F56BD745C2A144F4DC4C31E39A4A38F`.
- Build script `agent/build_windows.ps1` now uses `--windowed` instead of `--console` for subsequent builds.
- Desktop shortcut: `E:\Desktop\RemoteDeskPro-Agent.lnk` (target points to the EXE; pairing credentials are not embedded)
- Launch verification: **passed** using a temporary local-only WebSocket stub at `127.0.0.1:8765`; the EXE started, completed the agent `connected` handshake, remained alive, and was then stopped. No Render endpoint or production credentials were used.
- Server URL and pairing credentials remain configurable via `--server`, `--device-id`, `--secret`, `--dynamic-password` or the existing `RDP_*` environment variables. No pairing secrets were added to the shortcut or repository.
- Build artifacts, virtual environment and spec file remain locally ignored; no EXE or secrets were pushed to GitHub.


## Phase 7 — relay resilience and public release preparation (2026-11-21 IST)
- Updated `agent/host_agent.py`: explicit WebSocket open/ping/close timeouts, bounded receive queue, and an exponential reconnect loop (2–30 seconds) after transient relay/network errors. Invalid device credentials remain a fatal configuration error.
- Updated `backend/main.py`: host disconnect handling treats `OSError`/socket resets as normal disconnects and only marks a device offline when the disconnecting socket is still the currently registered host. A stale/replaced socket can no longer mark the newer connection offline.
- Static validation: Python compileall and `git diff --check` passed.
- Source-level local relay-reset test passed: three successful auth/connected handshakes across two deliberately injected WebSocket resets.
- Standalone EXE reconnect test did not pass: the rebuilt windowed EXE connected once but did not reconnect in the local simulated-reset harness. Do not publish this binary as a stable release until this discrepancy is resolved and the rebuilt EXE passes the same test. The earlier EXE launch/initial-handshake test is not sufficient evidence of reconnect behavior.
- Multi-session architecture review: login access tokens are stateless JWTs with no per-login revocation store; host uses its device secret, viewer uses a separate 15-minute device-scoped session token. Signing into the same account on host and viewer does not inherently invalidate either token. One active viewer per device is enforced; this is a per-device concurrency limit. Same-account host/viewer use has not yet been exercised with the real account on two live devices.
- Render `/api/health` checked during this task: HTTP 200, `status=ok`, `database=postgresql`. Live host/viewer session behavior after these source changes remains unverified.
- Release `v1.0.0` was not published because the standalone executable did not pass the reconnect regression test. Do not represent the source-level test as an EXE-level pass.

## Phase 4/4 - Native desktop, persistent sessions, and v1.0.0 release gate (2026-11-21 IST)

### Native Windows desktop app
- Double-click launch opens the native Tkinter desktop GUI; CLI/headless flags remain supported.
- First-run GUI supports account sign-in or account creation, then authenticated device pairing.
- GUI displays device ID and dynamic password with Copy and Rotate Password controls, explicit Disconnect, host-side approval dialog, live status and expandable diagnostics.
- Device ID remains stable across launches. Device secret, account token and dynamic password are protected with Windows DPAPI in %APPDATA%/RemoteDeskPro/config.json.
- Agent logs rotate at %APPDATA%/RemoteDeskPro/agent.log. Secrets are not written to logs.
- Password rotates on application restart or explicit rotation; the previous password is immediately invalidated.

### Session and relay lifecycle
- Account and viewer session JWTs use the configured 30-day session lifetime. Established WebSockets do not expire mid-session; viewer reconnect reuses its device-scoped token.
- Dynamic password has a 24-hour idle TTL; successful viewer connection refreshes the inactivity window. Manual rotation or agent restart immediately invalidates the previous password.
- Host WebSocket uses TLS CA bundle, keepalive, explicit timeouts and bounded reconnect backoff. Viewer sends application heartbeats and reports latency.
- Backend relays host online/offline/explicit-disconnect states and re-notifies a waiting host when a viewer is present after host reconnect.
- Replaced host sockets are closed; stale socket cleanup cannot mark a newer host offline.
- Each device permits one active viewer. Viewer registration/removal is atomic under the hub lock; the server sends `relay_ready` before auth and an explicit `viewer_rejected` event before close code 4429. Every session requires visible host approval; unattended access remains disabled.

### Frozen Windows build
- PyInstaller 6.22.3; Python 3.14.0; Windows 10 build 19045.
- Frozen EXE reconnect regression: PASS - 3 authenticated handshakes across injected WebSocket resets, 3 connection log entries, rotating log created. Harness uses an ephemeral local port: tests/smoke_frozen_reconnect.py.
- EXE: E:/GitHub-Vault/remote-desk-pro-main/agent/dist/RemoteDeskPro-Agent.exe
- Size: 21,580,391 bytes.
- SHA-256: 8B7432A861A1532234808F3A8CBBD5A16DE1A1D81974751CF78600C90AC9F778
- Existing Desktop shortcut path: E:/Desktop/RemoteDeskPro-Agent.lnk; target path is unchanged and points to the final EXE.
- GUI startup smoke: PASS — visible Windows titled `Remote Desk Pro` and `Link this computer`; `%APPDATA%/RemoteDeskPro/agent.log` created.

### Validation
- Python compileall: PASS.
- pytest: 10 passed (one upstream Starlette/httpx deprecation warning).
- Frontend TypeScript/Vite production build: PASS.
- git diff --check: PASS.
- Frozen EXE relay-reset test: PASS (3/3).
- Live Render E2E: PASS against `RDP_SERVER` after deployment of `2a08441`. Verified same-account registration/pairing, password rotation invalidation with existing viewer-token continuity, host approval, bidirectional clipboard relay, 185,000-byte chunked file transfer, explicit one-viewer rejection (`viewer_rejected`), heartbeat acknowledgement, and host reconnect while the viewer remained connected. The test creates synthetic @example.com accounts/devices; these test records were not deleted.
- Audit persistence: PASS — a read-only Supabase query on project `qxssuczpumsaqywifirv` confirmed 12 `rdp_audit_events` rows for the successful synthetic E2E device, including device pairing/password rotation, session request/approval, clipboard relay, file offer/receipt, and host disconnect. The test account is a technician, so the admin-only audit API was not used; direct read-only database verification confirmed persistence.
- Render service: remote-desk-pro-pj29 (srv-dc0917utlv9c739h7o30), branch main, auto-deploy enabled, verified URL RDP_SERVER; /api/health returns HTTP 200, status=ok, database=postgresql.
- Requested alias RDP_SERVER returns HTTP 404 and is not configured as the agent default.
- GitHub repository is PRIVATE. Release v1.0.0 can be published to repository collaborators; asset downloads require repository access. Repository visibility will not be changed as part of this release.
- Backend/frontend source commit `2a08441` is pushed to `main` and deployed on Render. Final Windows-agent reconnect backoff fix is pushed in `d4b88e3`; the E2E harness adjustment and documentation are committed. GitHub Release `v1.0.0` and verified EXE/checksum asset upload remain pending.


## 2026-11-21 - Remote input, single-instance, and public agent distribution

### Windows input and session safety
- Viewer input uses Pointer Events for mouse and touch, including pointer capture, pointer cancellation, context-menu suppression, wheel scrolling, and normalized image coordinates that account for letterboxed canvas rendering.
- Keyboard input uses explicit key-down/key-up lifecycle, maps browser modifier/navigation keys to PyAutoGUI names, suppresses repeated key-down events, and releases held keys when the viewer loses focus.
- Host input dispatch supports normalized primary-monitor mouse movement, left/middle/right button down/up, keyboard down/up including modifiers, vertical/horizontal scrolling, and release of held keys/buttons on viewer departure or relay teardown.
- Host startup enables per-monitor DPI awareness. Normalized coordinates are scaled from the MSS primary-monitor capture dimensions to the PyAutoGUI desktop dimensions and clamped to valid physical pixels.
- PyAutoGUI FAILSAFE is disabled for remote pointer movement; all input remains gated by explicit host approval. The backend validates supported input types, coordinate bounds, button IDs, key lengths, finite scroll values, and relays control packets only to an approved session.
- Both native GUI and headless host entrypoints enforce the Windows named mutex `Global\RemoteDeskProAgentMutex`. A duplicate launch is rejected; the GUI path attempts to restore and foreground the existing `Remote Desk Pro` window.
- Windows local input E2E: PASS. The automated `tests/smoke_host_input_windows.py` test opened a temporary Tk window and verified a real button click and text-entry key-down/key-up dispatch through the host-agent input dispatcher.
- Mutex verification: PASS for both `agent/desktop_app.py` and `agent/host_agent.py` duplicate acquisition paths.

### Public Windows agent download
- The public API route `GET /download/agent` serves `backend/downloads/RemoteDeskPro-Agent.exe` as an attachment with the Windows executable media type.
- Docker runtime copies the complete `backend/` directory, including the downloadable executable, into the Render image.
- Public URL after the Render deployment containing this commit is live: RDP_SERVER/download/agent
- The GitHub repository remains private; the Render download endpoint is the public distribution path and does not require GitHub repository access.

### Authoritative standalone build
- Build host: [redacted-host-name], Windows 10 build 19045.
- Python: 3.14.0; PyInstaller: 6.22.3; one-file, windowed executable with agent runtime dependencies bundled.
- Authoritative local executable: `agent/dist/RemoteDeskPro-Agent.exe`.
- Public distribution copy: `backend/downloads/RemoteDeskPro-Agent.exe`.
- Exact size: **21,586,937 bytes**.
- SHA-256: `C1BC99DCBC631DA6DC532F505B4620D908A0ECA71BAA2A968BA55DA90C529223`.
- The authoritative and distribution copies were byte-for-byte identical at checksum verification.
- Stale `agent/dist-release/` and `agent/build-release/` directories were removed. Only `agent/dist/` is the authoritative EXE output directory.

### Verification
- Backend suite: `python -m pytest -q` - **28 passed**, one Starlette/httpx deprecation warning.
- Frontend: `npm run build` - PASS (TypeScript build and Vite production bundle).
- Python compileall: PASS.
- `git diff --check`: PASS.
- Host input unit tests include DPI scaling across differing MSS/PyAutoGUI resolutions, mouse click dispatch, modifier lifecycle, scrolling, release-on-disconnect, and backend control validation.
- Public download route test: PASS; TestClient verified HTTP 200, attachment filename, executable content type, and payload size.
- Live Render deployment and public internet download were verified after the GitHub push: health HTTP 200 with PostgreSQL, application and manifest HTTP 200, and GET `/download/agent` HTTP 200 with the full executable downloaded and SHA-256 matched to the authoritative build.
- Full remote-control interaction through a real external viewer and production Render WebSocket is not claimed by the local Windows input smoke test; host consent remains mandatory and the agent captures the primary monitor only.


### Post-push CI and Render certification
- GitHub Actions run: `44896078456` for commit `f3defe6ddb1d0a0a09d0870a432837e2d8d89ae2` - **SUCCESS**.
- Backend job: **SUCCESS**; the `python -m pytest -q` workflow step completed successfully.
- Frontend job: **SUCCESS**; the `npm run build` workflow step completed successfully.
- Render build: `bld-dc0ndvfb9u1s73bnfea0` - **SUCCEEDED** for commit `f3defe6ddb1d0a0a09d0870a432837e2d8d89ae2`.
- Render deployment: `dep-dc0ndvfb9u1s73bnfe9g` - **SUCCEEDED**.
- Live public GET download verified from the internet: HTTP 200, content length 21,586,937 bytes, content type `application/vnd.microsoft.portable-executable`; downloaded SHA-256 exactly matched `C1BC99DCBC631DA6DC532F505B4620D908A0ECA71BAA2A968BA55DA90C529223`.
- Public download URL: RDP_SERVER/download/agent


### Live production remote-input E2E (2026-11-21)
- Added repeatable, modular Windows-hosted Playwright harness: `tests/e2e_remote_control_live.py`.
- Harness uses the existing DPAPI-protected `%APPDATA%\RemoteDeskPro\config.json` at runtime; credentials are never printed or committed to `.env` or the manifest.
- Browser: headless Chrome through Playwright, mobile emulation at 390×844 with touch enabled.
- Test target: temporary Tk window; verifies OS-level cursor coordinates, actual click callback, mouse-wheel callback, and keystrokes received by a native Windows entry control.
- Host approval: the real Remote Desk Pro consent dialog must be explicitly approved; the harness does not bypass consent.
- Temporary state file: `%TEMP%\rdp-live-input-e2e-state.json`; removed by harness cleanup. Test target process/window is terminated in `finally`.
- Browser session is closed after test; test script is retained for repeatable release verification.
- Playwright Python package installed in the user Python 3.14 environment; uses existing Chrome at `C:\Program Files\Google\Chrome\Application\chrome.exe` (no bundled browser download).
- Initial checks: Render `/api/health` reports `status=ok`, `database=postgresql`; one PyInstaller one-file process tree (one root instance with its expected bootloader child); agent has an established HTTPS connection to Render; DPAPI config fields are present; no credentials emitted.
- Execution outcome and measured latency are recorded in the following certification entry after the run.


### Live production remote-input E2E — interim result (2026-11-21)
- Headless Chromium successfully authenticated with the locally DPAPI-unsealed agent credentials, paired to the current device, and established approved Render relay sessions. Agent log recorded `Connected (Live)` after the real local consent action on successful runs.
- Real touch tap over the mobile-emulated viewer reached the Windows Tk target; its native click callback incremented to `1`.
- Mouse movement was observed through `pyautogui.position()` at the intended test-window region (scroll-target cursor sample: `(468, 495)`; target window client bounds are approximately x=88..848, y=111..631).
- Scroll did **not** pass: the target's Windows `MouseWheel` callback remained at zero. Inspection shows `host_agent.apply_control` computes `vertical=round(deltaY/100)` and calls `pyautogui.scroll(-vertical)`. On Windows, PyAutoGUI 0.9.54 passes that raw value directly as `mouse_event` `dwData`; Windows wheel messages require multiples of `WHEEL_DELTA=120`. A local Tk probe produced no wheel callback with raw `-7`; a scaled `-840` probe produced a wheel callback. This strongly isolates the production scroll defect to the host-agent wheel-unit conversion.
- Keyboard assertion was not completed because the current harness stops after the scroll failure; a later retry did not display the host-consent dialog within its wait window. No keyboard pass is claimed.
- Temporary Tk target process/window and `%TEMP%\rdp-live-input-e2e-state.json` are cleaned in the harness `finally` path. Headless browser contexts are closed; no test target window remains. Agent process tree still has exactly one root PyInstaller instance (with its expected one-file bootloader child).
- Required follow-up to complete certification: change Windows vertical/horizontal wheel dispatch to use `WHEEL_DELTA`-scaled values, rebuild and relaunch the standalone agent, then rerun the complete live touch/click/scroll/keyboard suite and capture final cursor coordinates and latency.


### Phase 4/5–5/5 — wheel fix, standalone rebuild, live E2E certification (2026-11-21)

**Production code change**
- `agent/host_agent.py`: introduced `_wheel_delta_units(delta)`; converts browser wheel deltas to integer Windows `WHEEL_DELTA` units (`120` per notch), preserves a signed minimum notch for every non-zero input, returns zero for zero input, and applies the converted integer to both vertical `pyautogui.scroll` and horizontal `pyautogui.hscroll` dispatch.
- Conversion boundary checks passed for `0`, `+1`, `-1`, `+49`, `-49`, `+100`, `-100`, `+720`, and `-720`; results preserve sign and minimum notch.
- `tests/e2e_remote_control_live.py`: expanded assertions for explicit OS cursor movement, vertical/horizontal wheel input, and keystrokes; horizontal Windows `WM_MOUSEHWHEEL` hook and cleanup included. Python compile check passed.

**Rebuilt standalone executable**
- Built with repository `agent/build_windows.ps1`: PyInstaller 6.22.3, Python 3.14.0, Windows 10, `--onefile --windowed`.
- Output: `agent/dist/RemoteDeskPro-Agent.exe`; distribution copy refreshed at `backend/downloads/RemoteDeskPro-Agent.exe` and byte/hash equality verified.
- Build timestamp (UTC): `2026-11-21T11:45:16.5113530Z`.
- Size: `21,589,028` bytes.
- SHA-256: `629129DAE894598E57C5B73A0AC4B76FAC718D3ACFEB886E6B55BB92DD161FB3`.
- Old agent was stopped before build; rebuilt agent relaunched. Final verification: exactly one logical root instance (two expected one-file process-tree entries), one established agent HTTPS connection to Render.

**Post-build live E2E matrix**
- Render `/api/health` and PostgreSQL: PASS (`status=ok`, `database=postgresql`).
- One agent instance / connected HTTPS relay: PASS.
- Headless Chromium mobile emulation, viewer auth and pairing: PASS on test attempts.
- Explicit host consent: PASS on two attempts; one later retry did not receive an approval acknowledgement and was cleaned up.
- Remote screen frame delivery: INCONSISTENT. One attempt timed out waiting for canvas frames; later attempt reached input dispatch.
- Touch tap and real Windows target click: PASS (native target click callback count reached 1).
- Cursor movement: PASS on the input-dispatch attempt; cursor target mapping used target coordinates `(468, 496)`; a final numeric cursor/latency sample was not retained in the harness report.
- Vertical scroll: PASS on one post-build attempt (native Windows target wheel callback count reached 2); another attempt did not register a wheel callback.
- Horizontal scroll: NOT VERIFIED / FAIL. Windows `WM_MOUSEHWHEEL` hook did not record a message in the attempted run; horizontal callback count remained 0. No pass claim.
- Keyboard: NOT COMPLETED; the test sequence stopped before the keystroke assertion on attempts that failed earlier. No pass claim.
- End-to-end round-trip latency: NOT CERTIFIED. The harness did not emit a complete metrics report because its failing assertions exited before report serialization. Do not infer latency from wall-clock test duration.

**Final cleanup and current state**
- Temporary Tk target window: 0.
- Headless Chromium processes: 0.
- `%TEMP%\rdp-live-input-e2e-state.json`: absent.
- Temporary desktop screenshot/diagnostic image: removed.
- Rebuilt agent: exactly 1 logical root instance; 1 established HTTPS connection to Render.
- Production certification remains PARTIAL pending stable horizontal wheel delivery, a successful keyboard assertion, and a complete numeric latency report. The rebuilt binary and source change are local; this batch did not push or redeploy the updated executable to Render.

## Phase 5/5 execution record — 2026-11-21 (NOT CERTIFIED)

- Status: **BLOCKED / PARTIAL**. Do not represent this revision as 100% certified.
- Native horizontal wheel implementation: ctypes Win32 user32 mouse_event with MOUSEEVENTF_HWHEEL = 0x01000 and signed 120-unit delta; the prior pyautogui.hscroll call was removed.
- Windows build: standalone PyInstaller --onefile --windowed; build timestamp UTC: 2026-11-21T12:12:09.5245155Z; size: 21590328 bytes; SHA-256: FF011ECEA158B1CD5389DDE72C13CF5992D056AEC5FBE03C504D34631A729A7C.
- Distribution artifact: backend/downloads/RemoteDeskPro-Agent.exe copied from agent/dist/RemoteDeskPro-Agent.exe.
- Build checks: py_compile and git diff --check passed.
- Live E2E attempt 1: Render session reached host approval, but touch tap did not register; test stopped before cursor, scrolling, and keyboard.
- Live E2E attempt 2: host approval acknowledgement timed out; no input assertions or latency samples were captured.
- Horizontal scroll: implementation rebuilt, NOT live-verified.
- Vertical scroll: NOT live-verified in this execution.
- Keyboard: NOT live-verified in this execution.
- Round-trip latency min/avg/max: N/A — zero valid samples.
- Test evidence: tests/e2e_remote_control_live_report.json (failure report; no credentials).
- Render /api/health: previously observed status=ok, database=postgresql; this does not prove the new binary is deployed.
- Deployment boundary: GitHub push triggers the configured Render auto-deploy; Render deployment of this commit and public download hash must be verified separately.
- Certification gate remains open until an approved live session passes touch, cursor, vertical wheel, native horizontal wheel, keyboard, and records non-empty latency metrics.
- Final local agent connectivity check: one logical agent process remains, but **0 established relay connections** were observed during final cleanup; do not describe it as healthy or online until connectivity is restored.
- Code and binary commit: 21d296d01e1f049cb22e38619faa04a0857b54a6


## Cloud-only implementation checkpoint (2026-11-21)
- Added root GET /health alias for the existing database-verified /api/health handler.
- Added GET /api/download/agent alias for the existing /download/agent handler. Both serve backend/downloads/RemoteDeskPro-Agent.exe; return 503 until a build artifact is present in the Render image.
- Added .github/workflows/build-windows.yml: Windows runner builds the one-file/windowed agent, reports size and SHA-256, publishes a latest-agent release asset, commits the EXE into the Render image context, and uploads a 30-day workflow artifact.
- The repository is private, so Render download routes serve the committed binary; they do not redirect unauthenticated clients to a private GitHub release asset.
- Added zstandard>=0.23,<1 to backend and agent requirements in preparation for the isolated transfer engine.
- NOT IMPLEMENTED/CERTIFIED: resumable transfer protocol, durable acknowledged-offset state, compression/decompression guards in the active relay, transfer UI pause/resume controls, and Windows live E2E. Existing transfer remains the prior 50 MiB / 192 KiB viewer-to-host flow. Existing input-dispatch modules were not edited.
- Pending verification: GitHub Actions run, Render deployment and both route HTTP checks, and local Windows E2E (host consent, touch/click, cursor, vertical/horizontal scroll, keyboard, transfer resume/compression, and latency min/avg/max).


## Cloud transfer primitive (2026-11-21)
- Added backend/file_transfer.py: resumable partial-file storage, transfer-ID validation, acknowledged chunk offsets, duplicate-chunk conflict detection, optional Zstandard decode, a 100:1 expansion-ratio guard, bounded 256 KiB–1 MiB chunks, maximum 50 MiB file size, streaming SHA-256 verification, and atomic final rename.
- Added tests/test_file_transfer.py for persisted resume, verified finalization, conflicting retransmission rejection, and incomplete-transfer rejection. The existing pytest CI job discovers this test module automatically.
- IMPORTANT INTEGRATION BOUNDARY: this storage primitive is not yet connected to the active /ws/viewer and /ws/host protocol, the Windows host agent receive loop, or the React file-transfer UI. Existing live file transfer remains the previous viewer-to-host implementation. Do not claim resumable/compressed file transfer is available until those integrations and their end-to-end tests pass.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 4eef31542972e1e36f8bd5c964b48a489abc828c.
- EXE size: 21708591 bytes.
- EXE SHA-256: DAFEF00F206834E1F3D956275B57F9E12016C1A393CEEF31BCDD45C40ED0BAE5.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


## Cloud-only continuation audit — 2026-11-21
- GitHub Actions Windows build: the `latest-agent` release was created/updated by `github-actions[bot]`; its `RemoteDeskPro-Agent.exe` asset is uploaded (21,708,591 bytes; SHA-256 `DAFEF00F206834E1F3D956275B57F9E12016C1A393CEEF31BCDD45C40ED0BAE5`). The workflow's binary+manifest commit is `6da5369ea36357bdfb3d564391198cb1c8702407`. The Actions run conclusion itself was not exposed by the available GitHub MCP run-list operation, so do not record a run ID or final run status from inference.
- Render auto-deployment for `6da5369ea36357bdfb3d564391198cb1c8702407` is **live** (`dep-dc0p3auc6qcc73bprrv0`).
- Live `GET /health` and `GET /api/health` both returned the expected health JSON with `status=ok` and `database=postgresql`.
- `GET /download/agent` returned a binary response larger than the web extractor's supported response size; the exact HTTP status and response headers were not surfaced by that extractor. The executable is present in the GitHub release and in the Render build input, but this check did not independently verify the live response's Content-Length or SHA-256.
- The new `backend/file_transfer.py` remains a storage primitive only. The active WebSocket relay still uses the older in-memory `hub.transfers` protocol; the Windows agent still writes directly to its selected save path; the React viewer still sends 128 KiB base64 chunks without acknowledgements, resume, compression controls, or SHA-256 confirmation. Do not advertise resumable/compressed transfers as implemented.
- Transfer persistence caveat: the current Render service is Free and no persistent disk is configured. Filesystem-backed partial transfer state would not survive instance replacement/redeploy without a persistent disk or external object storage. The present primitive is therefore process/instance durable only when its root remains available, not a production cross-deploy persistence guarantee.
- The existing native Windows input dispatch logic was not modified during this continuation.
- No GitHub Codespace was created or started during this continuation. The available GitHub MCP tool catalog did not expose an account-level Codespaces listing operation, so account-wide zero-active status was not independently queried.
- Next required implementation work: connect a consent-gated transfer protocol to both WebSocket endpoints and the Windows host agent, add acknowledgement/retransmission and reconnect state, expose progress/pause/resume/Zstandard controls in the React viewer, add relay/disconnect/compression/integrity tests, then run CI and live desktop E2E before certification.

## 2026-11-21 — Endpoint transfer protocol wiring (cloud implementation checkpoint)
- Backend relay: `backend/main.py` now accepts authenticated `transfer_*` JSON frames only after the per-device host-approval gate. It validates transfer IDs, 50 MiB file limit, 256 KiB–1 MiB chunk size, base64 payload decoding, chunk byte limits, and non-negative offsets, then forwards frames between connected endpoints. Render does not persist file bytes or partial state.
- Protocol messages: `transfer_init` (manifest), `transfer_chunk` (offset + base64 payload), `transfer_resume_req` (receiver next acknowledged offset), `transfer_ack` (next acknowledged offset), `transfer_complete` (receiver checksum result), and `transfer_error`.
- Windows host agent: added `agent/resumable_transfer.py`; after visible host approval the host asks the user to select a save destination, persists `.part` and JSON acknowledgement state beside it, acknowledges chunks, rejects conflicting/out-of-order chunks, optionally decodes Zstandard with a 100:1 expansion-ratio limit, verifies final SHA-256, and atomically renames only after verification. `agent/host_agent.py` handles init/chunk/complete frames; native input dispatch was not changed.
- React viewer: `frontend/src/App.tsx` uses 256 KiB chunks, browser SHA-256, acknowledged-offset progression, progress display, pause/resume, and a compression toggle. Zstandard sending is intentionally rejected because no browser Zstandard encoder is bundled. Browser sender state is memory-only; page reload recovery/IndexedDB is not implemented.
- Tests: `tests/test_file_transfer.py` additionally tests endpoint receiver persisted resume and final checksum rejection. `tests/e2e_remote_control_live.py` has not yet been extended to execute full transfer, simulated socket interruption/retransmission, or compressed transfer alongside native input checks. These checks remain required before certification.
- CI/build: source commits trigger `.github/workflows/ci.yml` and `.github/workflows/build-windows.yml` (the Windows workflow excludes manifest-only and binary-only paths). Verify CI, frontend build, Python tests, and the new EXE artifact after the final source commit.
- Persistence boundary: Render relay is stateless for transfer bytes. Endpoint `.part` files are durable on the Windows host disk. Browser sender state is memory-only at this checkpoint; do not claim page-reload recovery.
- Current status: partial protocol integration committed; full E2E and production certification pending. Existing verified horizontal/vertical scroll, touch, cursor, and keyboard dispatch logic was not edited.
- Laptop verification command (run only after the new Windows Actions artifact is published; replace the checksum with the new successful build's checksum):
```powershell
$ErrorActionPreference='Stop'; $base='RDP_SERVER'; $exe=Join-Path $env:LOCALAPPDATA 'RemoteDeskPro\RemoteDeskPro-Agent.exe'; New-Item -ItemType Directory -Force (Split-Path $exe) | Out-Null; Invoke-WebRequest "$base/download/agent" -OutFile $exe; $expected='REPLACE_WITH_NEW_ACTIONS_SHA256'; $actual=(Get-FileHash $exe -Algorithm SHA256).Hash; if($actual -ne $expected){throw "Build checksum mismatch; wait for new Actions artifact."}; Start-Process $exe; Start-Sleep -Seconds 15; python tests/e2e_remote_control_live.py
```

## Cloud-only repair checkpoint — 2026-11-21 (verification pending)
- Frontend CI failure root cause: `frontend/src/App.tsx` called `uploadPendingFile()` without its required numeric resume offset. Fixed to pass `transferOffset.current` (commit `0a9b5dd397fd77f4bbc19ea6c8a835e65ba84d75`).
- Backend CI failure root cause: the horizontal-wheel unit test called Windows-only `ctypes.WinDLL` on the Ubuntu runner. The test now injects a fake Win32 user32 API and asserts the native `MOUSEEVENTF_HWHEEL=0x01000` event and signed 120-unit delta (commit `31d5350ef5236fc694768f054b9cfe31c362a8e0`). Runtime dispatch remains native on Windows.
- Windows build workflow race: its generated binary/manifest commit could lose a fast-forward race against concurrent main pushes. Added `git pull --rebase origin main` before pushing generated output (commit `5acbe8f81c42dde7bab2b02f236507d4b2bed2c0`).
- Target foregrounding: added `_focus_target_at_cursor()` to use `WindowFromPoint`, `GetAncestor`, `ShowWindow`, thread-input attachment, and `SetForegroundWindow` before click, key, and wheel dispatch (commit `01791c1d6578bf6b877b0876b51abf6c785aea11`). Cursor coordinate scaling and the existing native wheel flags are unchanged.
- Prior Windows build run `44908247281`: PyInstaller succeeded and produced 22,260,644 bytes, SHA-256 `268C277220D1ABE4F09B6299775A15D0351106A5B9F1DF16B1951290829E0ACF`; release upload succeeded, but generated binary/manifest push failed because it was not rebased. This artifact was built from pre-repair source and is NOT the final repaired build.
- CI run `44908291028` failed: frontend TypeScript TS2554 at App.tsx:55 (missing offset argument); backend pytest failed because `ctypes.WinDLL` is unavailable on Linux. Fixes above now pushed; their new CI results must be checked before certification.
- NOT YET IMPLEMENTED: browser Zstandard encoding, IndexedDB transfer recovery, transfer E2E disconnect/resume + compressed checksum scenario, and a live end-to-end run covering all input events. The current UI still rejects Zstandard mode and retains the selected File/offset only in memory. Do not claim these features are complete.
- The live input E2E suite was inspected but not run in this cloud-only execution. It requires the enrolled Windows host, visible consent, Chrome, and the native desktop target. Touch/click/scroll/keyboard/RTT are not certified by CI.
- No GitHub Codespace was created or started in this execution. No Desktop Commander or local Windows tool was used.
- Current release SHA-256 remains the older published build until a new successful Windows Actions run completes and its release asset/hash is confirmed.

- Follow-up CI diagnosis: the initial Linux test fix exposed an additional expectation mismatch: Windows `pyautogui.scroll` consumes notch counts, while native horizontal `mouse_event` consumes 120-unit `WHEEL_DELTA`. Vertical dispatch now divides the converted delta by 120 before calling PyAutoGUI; horizontal remains native `MOUSEEVENTF_HWHEEL` with signed 120-unit delta (commit `739f887751123d989779cee2b3cfe487706935be`). CI rerun required.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 739f887751123d989779cee2b3cfe487706935be.
- EXE size: 22264493 bytes.
- EXE SHA-256: C474C1C0043CBB0C924F7BA1CA82DEA81745BD2933543651F1312C05924D0FAB.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 6adef95cb467ec8606c1475a1218412a85b435d0.
- EXE size: 22265653 bytes.
- EXE SHA-256: FF530A72CE602E294598A2477C4AB8765FA429B19695D4B26D481EBF25F434B4.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 156792d35f6de8bd0680e415e785226ec88cf1e5.
- EXE size: 22264270 bytes.
- EXE SHA-256: FE6E84A1A2288C00C1ECE8A4F8D31E6028CE28C529348DB0BA16E0151DF89035.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


## Browser Zstandard + IndexedDB + live transfer E2E checkpoint — 2026-11-21
- Browser Zstandard: added `@bokuweb/zstd-wasm@^0.0.27`; initialized the WASM encoder lazily and compresses each 256 KiB source chunk as a valid Zstandard frame before base64 relay. Vite excludes the WASM package from dependency prebundling and targets ES2020. Commits: `6adef95cb467ec8606c1475a1218412a85b435d0`, `05358986b69ea6878db2329ae9b9fc9e8255df39`.
- Browser persistence: added `frontend/src/transferStore.ts`, an IndexedDB store for transfer ID, filename, byte size, source SHA-256, chunk size, compression, acknowledged offset, original File/Blob, and update time. App restores the latest active transfer after reload and sends its manifest again after host approval. Acknowledged offsets are persisted before the next chunk is sent. Commits: `0243ea3cb781cb628f92a8ab84dde3cd1f0367bb`, `e7bed584ba6406f2fee4070cf813c20e10003f0d`.
- Transfer event flow: browser handles `transfer_resume_req`, `transfer_ack`, `transfer_complete`, and `transfer_error`; each chunk is sent sequentially and the receiver's verified SHA-256 result clears IndexedDB state.
- Live E2E harness: added a 2 MiB random payload test using Zstandard, a one-time injected viewer WebSocket close after the first transfer ACK, automatic reconnect/second visible host consent, selection of the same destination to reload endpoint partial state, and final source-vs-destination SHA-256 assertion. The existing touch, independent mouse click, cursor, vertical/horizontal wheel, keyboard and latency checks remain in the harness. Commits: `156792d35f6de8bd0680e415e785226ec88cf1e5`, `231aaaf4a3bae9fa4e39afcac158b3b78c44f873`, `a33c3c99da93d92809fdaa00a1680814a9129423`, `03150e20e0a6895990d0f392b48bf4e38a7530ad`.
- CI now compiles the live E2E Python harness with `python -m py_compile tests/e2e_remote_control_live.py`. Latest completed CI run `44909453879` on commit `b545df5b23d74f3f6a8f2fe549aa427a0b9faba7` passed both backend and frontend jobs. Earlier CI run `44909420926` on `a33c3c99da93d92809fdaa00a1680814a9129423` also passed both jobs.
- Windows Agent Build run `44909453862` for `b545df5b23d74f3f6a8f2fe549aa427a0b9faba7` was in progress at this checkpoint. The last successful prior EXE remains size 22,264,493 bytes, SHA-256 `C474C1C0043CBB0C924F7BA1CA82DEA81745BD2933543651F1312C05924D0FAB`, built from `739f887751123d989779cee2b3cfe487706935be`. Do not treat that as the newly built asset for this checkpoint.
- The live E2E harness has been extended but not executed in this cloud-only session. Its runtime requires the enrolled Windows host, visible consent and GUI save dialogs; CI only syntax-checks the harness and runs unit tests. Do not claim live transfer/input certification until the laptop command passes.
- No Desktop Commander, local Windows tools or GitHub Codespaces were used. No Codespace was created by this workflow.

## Final browser transfer + CI + Windows release checkpoint — 2026-11-21
- Latest main before this manifest entry: 99d563d36cbb81a0b54f2bd2b7e577653b37f44d.
- Final CI run: 44909597905, source 99d563d36cbb81a0b54f2bd2b7e577653b37f44d, conclusion SUCCESS (backend and frontend). Prior source CI run 44909453879 on b545df5b23d74f3f6a8f2fe549aa427a0b9faba7 also passed.
- Windows Agent Build: run 44909453862, source b545df5b23d74f3f6a8f2fe549aa427a0b9faba7, conclusion SUCCESS. latest-agent GitHub Release asset updated at 2026-11-21T13:35:15Z.
- Latest verified release asset: RemoteDeskPro-Agent.exe, size 22,263,828 bytes, SHA-256 A6961C8F9CDD64B07FFA8F88FFBA8B20036C2317DF8EFF3E7E6C37246297E43B. Release: https://github.com/lokeshmakhijani1-debug/remote-desk-pro/releases/tag/latest-agent . Hash is taken from the published release notes.
- Implementation commits: Zstandard dependency 6adef95cb467ec8606c1475a1218412a85b435d0; Vite WASM config 05358986b69ea6878db2329ae9b9fc9e8255df39; IndexedDB helper 0243ea3cb781cb628f92a8ab84dde3cd1f0367bb; React Zstandard/resume flow e7bed584ba6406f2fee4070cf813c20e10003f0d; transfer interruption E2E 156792d35f6de8bd0680e415e785226ec88cf1e5; socket interruption and mouse click checks 231aaaf4a3bae9fa4e39afcac158b3b78c44f873; dialog title fixes a33c3c99da93d92809fdaa00a1680814a9129423 and 03150e20e0a6895990d0f392b48bf4e38a7530ad; CI py_compile gate b545df5b23d74f3f6a8f2fe549aa427a0b9faba7; transfer implementation manifest 99d563d36cbb81a0b54f2bd2b7e577653b37f44d.
- Laptop verification command (run from local repository root): git diff guards abort if tracked local edits exist; git reset --hard origin/main updates tracked files only and leaves untracked/ignored agent credentials untouched. It downloads the private release using authenticated GitHub CLI, verifies the exact release SHA-256, restarts one agent process, then runs the live E2E suite:
```cmd
git diff --quiet && git diff --cached --quiet && git fetch origin && git reset --hard origin/main && powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $repo='lokeshmakhijani1-debug/remote-desk-pro'; $dir=Join-Path $env:LOCALAPPDATA 'RemoteDeskPro'; New-Item -ItemType Directory -Force $dir | Out-Null; gh release download latest-agent --repo $repo --pattern RemoteDeskPro-Agent.exe --dir $dir --clobber; $exe=Join-Path $dir 'RemoteDeskPro-Agent.exe'; $expected='A6961C8F9CDD64B07FFA8F88FFBA8B20036C2317DF8EFF3E7E6C37246297E43B'; $actual=(Get-FileHash $exe -Algorithm SHA256).Hash; if($actual -ne $expected){throw 'RemoteDeskPro-Agent.exe SHA-256 mismatch'}; Get-Process -Name 'RemoteDeskPro-Agent' -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Process -FilePath $exe -WorkingDirectory $dir; Start-Sleep -Seconds 15; py tests\e2e_remote_control_live.py"
```
- Live Windows input and transfer E2E has not been executed by the cloud workflow. The laptop command is the required final runtime verification; do not mark the application fully certified until its report is PASS.
- No Desktop Commander, local Windows tools or GitHub Codespaces were used. No Codespace was created or started in this work.
## Desktop release installation — 2026-11-22
- Latest GitHub Release: https://github.com/lokeshmakhijani1-debug/remote-desk-pro/releases/tag/latest-agent
- Release asset: RemoteDeskPro-Agent.exe (22264723 bytes).
- Installed Desktop executable: %USERPROFILE%\Desktop\RemoteDeskPro.exe (resolved path: C:\Users\hp\Desktop\RemoteDeskPro.exe).
- Verified SHA-256: B827E7EB509DC5916D2E8E2DA73E2CD384A8C319D5978A9481E837961BC56ABD.
- PE subsystem: Windows GUI (2); no console subsystem.
- Launch verification: latest standalone executable started successfully; process PID 7424 remained running for 10 seconds with a visible GUI window (title: Remote Desk Pro).

## Host keepalive, mobile input, file-consent, and viewer gesture hardening — 2026-11-22
- Host relay now retries transient network/proxy disconnects at a fixed 2-second interval and uses a 5-second WebSocket ping/pong heartbeat. The Windows desktop GUI holds ES_CONTINUOUS | ES_SYSTEM_REQUIRED while open and clears the execution state on GUI close.
- File transfer follows the active transfer_init WebSocket flow. The Windows desktop app presents a top-most Tkinter Accept/Decline dialog on its main GUI thread, displays filename and byte size, and saves accepted transfers under the host user's Downloads folder. The endpoint receiver retains resumable chunk state and verifies SHA-256 before finalizing.
- Mobile keyboard mode now uses a visible floating input field with autocomplete/correction/capitalization disabled, input and IME composition handling, immediate text WebSocket events, and Enter/Backspace/Tab/Escape key packets. The backend validates the event schema; the host uses PyAutoGUI for ASCII alphanumeric input and clipboard Ctrl+V for spaces/Unicode/special characters.
- Clipboard direct paste is a distinct authenticated clipboard_paste event that copies via pyperclip and invokes standard Ctrl+V. The viewer supports 1.0x–3.0x pinch/button zoom, clamped one-finger pan while zoomed, and tap-to-click using normalized remote coordinates.
- Viewer visibility resume refreshes device presence and sends an immediate heartbeat; a missing heartbeat acknowledgement closes and reattaches the viewer WebSocket.
- Local validation on 2026-11-22: Python compilation PASS; pytest 49 passed (one upstream Starlette/httpx deprecation warning); frontend TypeScript/Vite production build PASS; git diff --check PASS.
- tests/e2e_remote_control_live.py now includes headless Chromium mobile keyboard, clipboard paste, visibility-resume, zoomed touch-pan/tap, host file-consent, reconnect/resume, and Downloads SHA-256 checks at 390x844 with touch enabled. The expanded live test has not yet been run; do not certify the live Windows-to-Render path until its report is PASS.
- No .env files or secret values were changed. Deployment target remains Render RDP_SERVER; Vercel is not used.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: c5a4aaf7c3fb37b6d3729926570578b442060c4c.
- EXE size: 22272555 bytes.
- EXE SHA-256: AA0C90E13EE22EAB4871AA89D88D69CEE5339EAABB65845F8B35B7B57013B1A0.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


## Frontend TypeScript repair — 2026-11-22
- Fixed `frontend/src/App.tsx`: declared `SESSION_STORAGE_KEY` and the `PersistedSession` interface matching the existing `{ sessionId, deviceId, viewerToken }` sessionStorage payload; changed the End button to `onClick={() => disconnect()}` so React's mouse event is not passed as the boolean `explicitEnd` argument.
- Commit: `11ad77c2d5bcbcfe9adb1e9138703ea94f8b79f0`.
- Verification: GitHub frontend CI `npm run build` PASS; backend CI remains FAIL on the pre-existing `tests/test_input_dispatch.py::test_text_input_uses_clipboard_and_pastes_into_focused_host` assertion (52 passed, 1 failed; `host_agent.py` and tests were intentionally not changed). Render service `remote-desk-pro-pj29` auto-deployed commit `b8f23b98e77b6d3ff86e342cda1ebd8136f37d13` and reached status `live` at 2026-11-22T10:35:44Z; Docker `npm run build` completed successfully. Live mobile Playwright gate was not executed: GitHub workflow-dispatch is not exposed by the connected GitHub actions, and the available browser automation service refused to start due to insufficient credits. Do not claim the mobile keyboard, touch-pan, clipboard, file-consent, or visibility-resume checks passed.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 11ad77c2d5bcbcfe9adb1e9138703ea94f8b79f0.
- EXE size: 22269781 bytes.
- EXE SHA-256: 7CB5AC6E6A7D9374C7E4F0999FA4E80652623F47CBBB843A2FB4A286A272E101.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


## Remote text-input clipboard regression fix — 2026-11-22
- Fixed `agent/host_agent.py` in `apply_control()` so clipboard paste is used for text containing spaces or Unicode; only ASCII alphanumeric text uses `pyautogui.write()`. This aligns the legacy control handler with the mobile `apply_text()` path and prevents spaces from being injected through the direct typing branch.
- The existing test `test_text_input_uses_clipboard_and_pastes_into_focused_host` expects clipboard copy followed by Ctrl+V for `mobile typing`; the fake clipboard and PyAutoGUI mocks make this deterministic in Linux CI without requiring an X11 display.
- Source fix commit: `9d478dbaf7e217e61d2459b1a894bfac1b270f83`.
- Backend pytest, GitHub CI, and the Windows `latest-agent` rebuild are pending; update this checkpoint only after workflow results are verified.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 9d478dbaf7e217e61d2459b1a894bfac1b270f83.
- EXE size: 22270779 bytes.
- EXE SHA-256: E9370C5FFB0A241CED19025723286058FCA46DFA1FCFF325E96F6F6DFC13B0BA.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 67e9baa826165527b49daf1ad86f68881baed236.
- EXE size: 22271121 bytes.
- EXE SHA-256: 41A46C571EB5C1B3AA85E6C54AF741F36EB2654478F42D5CBED05C8E012B7379.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 250aff6277c4bacc50ac6746fdb10bda270b8367.
- EXE size: 22282807 bytes.
- EXE SHA-256: 6145BD373CDD8BC28253AF8F35D9DE53EA2C15FCC58F7973EBDD3D931D6CBC5A.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 2648cf9c9e360b1967a4bc9d90508d84ff587b0f.
- EXE size: 61075630 bytes.
- EXE SHA-256: 0E66CDA3AD5C37B321699AFC651EE12FD8CA76E62E8D9CD96F5CC9F63A15FBAE.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


## Phase 7 — input relay lifecycle, visible privacy banner, and session security recording (2026-11-22)

### Input and session lifecycle repairs
- Mobile IME composition completion now sends the completed input value (falling back to the composition payload only when the input value is empty), rather than sending only the final composition fragment.
- Clipboard paste now uses a request ID and waits for a host-generated `clipboard_ack`; the viewer no longer reports success optimistically. Host paste errors are returned as a failed acknowledgement.
- Backend returns an explicit `input_pending` event when text or clipboard input arrives before host approval.
- Viewer `viewer_end` now clears approval, sends `viewer_left` to the host, and releases the active viewer socket. An abrupt viewer transport disconnect also clears approval and sends host cleanup while retaining the authenticated owner reservation for same-user reconnect; reconnect requires fresh host approval.
- Host reconnect signaling preserves the waiting viewer ID. Existing transfer-init/resume/chunk handlers remain approval-gated; a pending transfer is re-issued by the viewer after `host_approved`.

### Host privacy and recording
- Added `agent/privacy_overlay.py`: an always-on-top, full-screen, visibly labeled maintenance banner. Local emergency unlock: `Ctrl+Alt+Shift+U`. It is removed on explicit viewer end, viewer transport loss, or host-agent disconnect.
- Viewer toolbar now provides a Privacy Banner toggle and an Auto banner checkbox for session start.
- **Pure blank/hidden-screen mode and `WDA_EXCLUDEFROMCAPTURE` are intentionally not enabled.** The supported capture path uses MSS and does not guarantee that excluding an overlay from capture preserves the underlying desktop stream; hiding the technician's activity from the physical user would also defeat visible-session transparency. The implemented banner remains visible to the local host.
- Added `agent/session_recorder.py`: after the host explicitly approves a viewer, a background worker records the primary display to `%USERPROFILE%\\Videos\\RemoteDeskPro-Recordings\\session_<device_id>_<timestamp>.mp4`. The host consent dialog discloses local recording. The worker finalizes the MP4 and appends session start/end, viewer ID, file size, and SHA-256 to `audit_log.jsonl` in the same folder.
- Viewer session header shows a subtle `REC` indicator when the host confirms recording startup. Recording failures are logged locally and do not bypass or weaken host consent.

### Dependencies, packaging, and modified files
- New agent dependency: `imageio-ffmpeg>=0.6,<1` for bundled H.264 MP4 encoding. No new external API keys or OAuth credentials.
- PyInstaller packaging updated in `agent/build_windows.ps1` and `.github/workflows/build-windows.yml` to collect `imageio_ffmpeg` and include `session_recorder` and `privacy_overlay`. No standalone PyInstaller .spec file exists in the repository; the current build uses explicit CLI arguments.
- Modified: `backend/main.py`, `frontend/src/App.tsx`, `frontend/src/styles.css`, `agent/host_agent.py`, `agent/requirements.txt`, `agent/build_windows.ps1`, `.github/workflows/build-windows.yml`, `README.md`, `tests/test_input_dispatch.py`, `tests/test_session_lifecycle.py`.
- Added: `agent/privacy_overlay.py`, `agent/session_recorder.py`, `tests/test_session_security.py`.
- No recordings, audit output files, credentials, or generated executables are committed. Recording outputs are created only on the approved host machine.

### Verification checkpoint
- Added unit coverage for the recorder worker's file finalization and audit SHA-256, non-Windows privacy-banner gating, and backend privacy-mode validation.
- GitHub Actions backend/frontend tests and Windows PyInstaller packaging are triggered by the source commits; final results and Render deployment health are pending this checkpoint.
- Cloud unit tests do not certify physical Windows overlay rendering, global keyboard behavior, or live host desktop recording; those require an interactive Windows host smoke test.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 14bb352492ec767550de2623d5631a0860f39a9e.
- EXE size: 61074628 bytes.
- EXE SHA-256: 23F3318E15FA31D3837B6AD2C1AEA17EF440B88C3ABC567B05EA515DD836F383.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 7d985e14328e219a2f840bb3fb00ae89948d96a7.
- EXE size: 61075422 bytes.
- EXE SHA-256: 5FDA38A2B86BFB95D48AC9AD5CE8F01F3FF8348A3698321C4A3DC240F8B931C0.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 9c31b230f8808638bd9baa3a9bf6fc0ef0362e31.
- EXE size: 61076269 bytes.
- EXE SHA-256: 5B3F615F40C9D74B192EFE4CCCF927FE0F2D9DB937E5339EA243FFBCA11EF0DF.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 6655adc64d5b75c62c5b6982fc35f12a59a4afb7.
- EXE size: 61076234 bytes.
- EXE SHA-256: A81EA5D7D40CE8E14C3310CF3189F637DD41D9DE39A5D6BB1E0CD676A32C6795.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


### Follow-up cloud E2E compatibility fix
- `ask_file_consent()` now accepts both synchronous and asynchronous consent callbacks. This keeps production Tkinter consent asynchronous while allowing deterministic synchronous consent adapters in headless integration tests and external embedders.
- Live cloud E2E exercised real Render WebSocket text relay, clipboard acknowledgement/paste, privacy-banner on/off, frame delivery, and resumed file-transfer setup. Those checks passed before the transfer test exposed the callback awaitability mismatch; the callback contract is now normalized.
- Follow-up source commit: `d2788147e09bca55af574ed8ca958aa57fc7d3af`; CI, Windows packaging, and the next live cloud E2E run are pending.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: d2788147e09bca55af574ed8ca958aa57fc7d3af.
- EXE size: 61076692 bytes.
- EXE SHA-256: CCB127E8375FBE0DC4097BA445D7E2065A3BB4F6C602BCFB113D336A444A9AB4.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


## Live cloud E2E file destination correction
- The initial post-callback E2E retry successfully completed the resumable transfer protocol and receiver-side SHA-256 verification, but the test asserted against a separate temporary path. Production `transfer_init` intentionally uses `downloads_destination()` (the host Downloads folder), not the legacy `choose_save_path()` hook.
- The headless test now overrides `host_agent.downloads_destination()` to direct the synthetic host receiver to its isolated temporary destination. This preserves production behavior while ensuring the E2E checksum assertion inspects the exact file written by the receiver.
- A fresh live cloud E2E run is required before certification; this correction is not considered verified until that run passes.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 554af56b32aca79f4ba21e847501e368d1d1d9b8.
- EXE size: 61077228 bytes.
- EXE SHA-256: 79BC62F6E3A5939ED91F790132D2D4153D441566EBA8F0D162353DFC29A4247A.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 717d7d3f7381b75ca9d68fbae009ea12ced80043.
- EXE size: 61079075 bytes.
- EXE SHA-256: 4C7C78E89A8C10C668EA9EDD66A05BC2D53C898043BE160F489C769390694BCA.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 4e67043d399db40207b2ff7779efd835c574fd75.
- EXE size: 61078315 bytes.
- EXE SHA-256: 560A39F25AC5924541F54B700D4306147E3BE7331F1FEA10D46690F24063F4A1.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 96282cfff42f1a0a226eb29cabf1bd367d436164.
- EXE size: 61081181 bytes.
- EXE SHA-256: 4CA6971A2705719108F1C7965C2ECC3E655276181C7BD93D9BA28662C95A429E.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 9dd349869a17010b2d5247c0f1f340efe19bb435.
- EXE size: 61080619 bytes.
- EXE SHA-256: E222C22F150A2D2EF502239DAF66BB0CDECAD06508677C2A93E52B865CFEC82F.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: ec23a50041ba78832b05b36029fc3d6b19469c3e.
- EXE size: 61078668 bytes.
- EXE SHA-256: 871D48EDE4257C357230DEE39F9FD5380F74CE94D264EFDCA3EA9493E07540F0.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: beebd909a11d1204ca50f4c4867e21cb622975e9.
- EXE size: 61079038 bytes.
- EXE SHA-256: 0089192DFBA262E32426C99F0330D413A93508180D0665A7E3EB7CED4D731C60.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


## V2 bidirectional automation branch
- `agent/workflow_engine.py`: opt-in semantic input recorder and normalized-coordinate adaptive replay; typed text and clipboard payloads are excluded; saves to `project_memory/workflows/` (APPDATA for frozen Windows builds).
- `agent/telemetry.py`: thread-safe FPS, ping, upload and download throughput counters for the host diagnostics HUD.
- `agent/host_agent.py`: exponential reconnect backoff, telemetry integration, privacy-screen-gated workflow recording, and `--viewer` embedded-client mode.
- `agent/desktop_app.py`: unified host console with embedded web viewer launch, workflow recording toggle and local replay control.
- `agent/requirements.txt`: adds `psutil`, Windows process/window metadata support, and `pywebview` for the embedded viewer.
- `Dockerfile` passes `VITE_CONTACT_EMAIL` into the Vite build; Render config exposes it as a manually supplied environment variable.
- `agent/build_windows.ps1`: local one-file V2 packaging command with embedded WebView, workflow, telemetry and Windows process metadata dependencies.
- `.github/workflows/test-and-build-v2.yml`: Windows regression/unit/stress/fault-injection tests, full-history Gitleaks scan, frontend build, and one-file Windows executable artifact.
- `test_instructions.json`: non-interactive dependency, regression, E2E, stress, security and fault-injection runner commands.
- Runtime endpoints and contact data are environment-provided (`RDP_SERVER`, `RDP_BASE_URL`, `CORS_ORIGINS`, `PUBLIC_BASE_URL`, `SUPPORT_EMAIL`, `VITE_CONTACT_EMAIL`). Production `APP_SECRET_KEY` must be unique and at least 32 characters.
- User-generated workflow JSON is ignored by `.gitignore` and must not be committed.

- V2 host-to-viewer file transfer: `agent/host_agent.py` queues a local file, persists its source path/hash/acknowledged offset in the host profile, sends 256 KiB chunks, resumes from viewer-acknowledged offsets after relay reconnect, and only clears the checkpoint after viewer SHA-256 verification.
- V2 viewer-side incoming transfer: `frontend/src/App.tsx` asks the viewer to accept, buffers chunks, acknowledges each offset, verifies SHA-256, then triggers a browser download. The current receiver resumes across WebSocket reconnects while the viewer page remains open; a full page reload restarts that incoming transfer from offset zero.

 
## V2 CI and security audit checkpoint — 2026-11-25
- Feature branch: `feature/v2-bidirectional-automation`; all V2 CI edits remain isolated from `main`.
- V2 validation now runs on `ubuntu-latest`; the `windows-latest` job is reserved for the PyInstaller executable build and SHA-256 artifact verification. `workflow_dispatch` remains enabled.
- Gitleaks runs on Ubuntu with full checkout history (`fetch-depth: 0`) to scan Git history; this scan has not yet completed because the repository's hosted jobs are failing before runner allocation.
- Issue #2 records six runs failing with `runner_id: 0`, no runner name, no steps and no job logs. Runner labels are valid standard labels. Billing/minutes quota is a plausible cause but is not confirmed by available API evidence.
- A targeted current-branch source/config/log scan found no high-severity credential-pattern matches in 55 inspected text files. This is not a complete all-commits/all-branches audit and is not public-release clearance.
- Public visibility gate: **NO — keep the repository private** until full-history Gitleaks results and branch-history review are clean, and any exposed credential is rotated/revoked.


## Phase 5/5 — local workflow history and privacy boundary (2026-11-26)
- Workflow storage defaults to `%APPDATA%\\RemoteDeskPro\\workflows\\` on Windows for both frozen and source-run agents; `RDP_WORKFLOW_DIR` remains an explicit test/portable override.
- A completed recording is detected by the desktop GUI and prompts for a workflow name, comma-separated tags and notes. The workflow is atomically renamed and annotated in local JSON; unnamed workflows can be retained.
- Added a local Workflow History window with selection and replay. Local workflow metadata explicitly defaults to `is_public=false`; the UI states that nothing is uploaded or shared.
- Added `annotate_workflow` and `list_workflows` APIs in `agent/workflow_engine.py`; metadata validation constrains names, tags and notes, and annotation refuses paths outside the configured workflow directory.
- Local schema fields: `schema_version`, `created_at`, `updated_at`, `name`, `tags`, `notes`, `is_public`, `coordinate_space`, `recorded_screen`, `step_count`, `steps`, and privacy flags. Private workflow files remain excluded from Git by `.gitignore`.
- Ports/endpoints: no new network endpoint or listening port is introduced by local workflow history.
- Verification added: APPDATA path selection, metadata sanitization/local-only defaults, and JSON-only history enumeration tests.
- Explicit remaining implementation gates: public community publishing/import APIs and database schema are not implemented; current recording captures normalized mouse/key/scroll actions and foreground process/window context, not complete ARIA/OCR semantic anchors; replay still uses process/window context plus normalized/window-relative coordinates and does not yet implement full UIA → OCR → coordinate fallback, popup recovery, or dynamic readiness waits. These are not completed capabilities.
- Release gate: the existing V2 Windows workflow produces a 14-day Actions artifact, not a public stable GitHub Release. Do not publish a release asset or deploy Render from this feature branch until full tests and separate release approval.


## Windows V2 build and optional public prerelease
- The feature-branch Windows build now names the binary `RemoteDeskPro-Agent.exe`, emits a SHA-256 sidecar, and retains the Actions artifact for 30 days.
- A public prerelease is gated behind an explicit `workflow_dispatch` input `publish_prerelease=true`; it runs only from `feature/v2-bidirectional-automation` and only after unit/frontend/security and Windows packaging jobs pass.
- The prerelease tag format is `v2.0.0-rc.<run_number>`; the downloadable executable and checksum are attached to the GitHub Release. This does not deploy Render and does not modify `main`.
- Local Windows build entrypoint: `powershell -NoProfile -ExecutionPolicy Bypass -File agent/build_windows.ps1`. Windows PyInstaller is required for a Windows `.exe`; Google Colab/Linux cannot cross-compile a native Windows executable using PyInstaller.


## Phase 5 community API and adaptive replay (2026-11-26)
- API: POST /api/workflows/publish (authenticated, explicit is_public=true, rejects local-only/sensitive data, 2 MB cap); GET /api/workflows/community (authenticated public-only listing); POST /api/workflows/import/{id} (public-only import returned as local/private).
- Database: rdp_community_workflows model in backend/database.py. Uses configured DATABASE_URL and existing SQLite WAL fallback when SQLite is selected. PostgreSQL migration: supabase/migrations/20261126170000_workflow_community.sql.
- Privacy: agent-local JSON remains in %APPDATA%\RemoteDeskPro\workflows\. Browser dashboard requires file selection, separate Make Public toggle, and Publish click before sending. API rejects is_public=false, privacy.local_only=true, typed/clipboard flags and sensitive field names. Community queries/imports filter is_public=true.
- Frontend: Workflow History enables explicit local JSON selection/publishing; Community Library lists public workflows and downloads imported JSON marked local/private. Browser cannot silently read APPDATA.
- Agent: agent/adaptive_replay.py implements UIA -> OCR -> window-relative/normalized coordinate fallback, bounded readiness polling, explicit safe popup-handler hooks, and Ctrl+A focus verification. agent/workflow_engine.py records nearby UIA name/role/bounds and click-adjacent OCR anchors; printable keystrokes and field values are not stored.
- Optional Windows dependencies: pywinauto and pytesseract. Tesseract OCR executable must be installed separately; absent optional tools degrade to coordinate anchors.
- Added tests: tests/test_workflow_community.py (5 privacy/API tests) and tests/test_adaptive_replay_10_envs.py (10 environment simulations). Latest CI determines complete suite count.
- No new network port. No Render deployment or production environment changes. Feature branch pushes trigger CI/security/Windows executable packaging.


## Phase 5 community API and adaptive replay (2026-11-26)
- API: POST /api/workflows/publish (authenticated, explicit is_public=true, rejects local-only/sensitive data, 2 MB cap); GET /api/workflows/community (authenticated public-only listing); POST /api/workflows/import/{id} (public-only import returned as local/private).
- Database: rdp_community_workflows model in backend/database.py. Uses configured DATABASE_URL and existing SQLite WAL fallback when SQLite is selected. PostgreSQL migration: supabase/migrations/20261126170000_workflow_community.sql.
- Privacy: agent-local JSON remains in %APPDATA%\RemoteDeskPro\workflows\. Browser dashboard requires file selection, separate Make Public toggle, and Publish click before sending. API rejects is_public=false, privacy.local_only=true, typed/clipboard flags and sensitive field names. Community queries/imports filter is_public=true.
- Frontend: Workflow History enables explicit local JSON selection/publishing; Community Library lists public workflows and downloads imported JSON marked local/private. Browser cannot silently read APPDATA.
- Agent: agent/adaptive_replay.py implements UIA -> OCR -> window-relative/normalized coordinate fallback, bounded readiness polling, explicit safe popup-handler hooks, and Ctrl+A focus verification. agent/workflow_engine.py records nearby UIA name/role/bounds and click-adjacent OCR anchors; printable keystrokes and field values are not stored.
- Optional Windows dependencies: pywinauto and pytesseract. Tesseract OCR executable must be installed separately; absent optional tools degrade to coordinate anchors.
- Added tests: tests/test_workflow_community.py (5 privacy/API tests) and tests/test_adaptive_replay_10_envs.py (10 environment simulations). Latest CI determines complete suite count.
- No new network port. No Render deployment or production environment changes. Feature branch push triggers CI/security/Windows executable packaging.

- CI: feature-branch workflow runs Python regression/privacy/10-environment tests, frontend build, full-history Gitleaks, and Windows PyInstaller. Live cloud E2E runs when repository secret RDP_BASE_URL is configured; otherwise it is explicitly skipped. No production secret is added by this change.

- Production Supabase migration applied successfully to RemoteDeskPro project qxssuczpumsaqywifirv; recorded migration version 20261126094251. Verified public.rdp_community_workflows exists with RLS enabled, public-only CHECK constraint, 2 MiB row-size constraint, owner FK, and SELECT policy limited to is_public=true. Table was empty at verification. Render was not deployed.


## V2 release security scan exception (2026-11-26)
- Added `.gitleaks.toml` with default Gitleaks rules retained (`[extend] useDefault = true`).
- A rule-specific AND-scoped allowlist extends only the default `generic-api-key` rule and matches the exact `PROJECT_MANIFEST.md` path, the two historical finding commits (`09bad163435de687eb0be82b4f0206cd25d21abb`, `cb66a236aa4efa6671522d1d95052cb481b5a0b3`), and a Gitleaks finding match containing a SHA-256 label followed within 40 characters by exactly 64 hexadecimal characters (`regexTarget = "match"`). All other default rules and generic-api-key findings remain enabled.
- This exception is limited to the two documented public SHA-256 digest findings. It does not disable general secret scanning or allow arbitrary API keys/tokens.
- V2 prerelease build and public asset details will be recorded here only after the workflow, executable, and checksum are verified.


## V2 public prerelease — verified (2026-11-26)
- Release: [v2.0.0-rc.46](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/releases/tag/v2.0.0-rc.46) (public GitHub prerelease; not stable).
- Workflow run: [#46](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/actions/runs/45810421042), dispatched on `feature/v2-bidirectional-automation` at commit `591c80b4733219ccbf0c06ebb882603f4c1d01a0` with `publish_prerelease=true`.
- Verified jobs: Python regression/frontend build SUCCESS; full-history Gitleaks SUCCESS; Windows V2 executable SUCCESS; prerelease publish SUCCESS. Live cloud E2E was skipped because repository secret `RDP_BASE_URL` is not configured.
- Executable: [RemoteDeskPro-Agent.exe](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/releases/download/v2.0.0-rc.46/RemoteDeskPro-Agent.exe) (69,468,639 bytes).
- SHA-256: `967EE16823F4512261B765EE59F8999A24E1D0BE39ADAB1BACBED537B363F104`. The Windows build job's `Get-FileHash -Algorithm SHA256` output matches the GitHub Release API asset digest.
- Checksum file: [RemoteDeskPro-Agent.exe.sha256](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/releases/download/v2.0.0-rc.46/RemoteDeskPro-Agent.exe.sha256).
- Release assets are attached to the GitHub Release. No Render deployment was triggered.


## V2 mobile control and explicit video recording update — 2026-11-26
- Frontend frontend/src/App.tsx: persistent sidebar preference in localStorage; mobile/tablet slide-in drawer behavior; touch-friendly floating action dock with drag repositioning and grid actions for Mouse, Keyboard, Privacy, File Transfer, Start/Stop Recording, Recording Settings, and Disconnect; live REC mm:ss elapsed badge.
- Frontend frontend/src/styles.css: responsive drawer overlay, mobile dock grid, safe-area-aware FAB placement, touch-sized controls, and recording settings modal styles. The full remote toolbar remains available on desktop.
- Agent agent/host_agent.py: removed automatic MP4 recording from host approval. The host now reports recording=false on approval and accepts explicit recording_control start/stop messages; desktop-agent requests are queued and handled by the active host loop. Recording is finalized on stop, viewer departure, and disconnect.
- Agent agent/session_recorder.py: duration cap (maximum four hours), retention count (1–100), storage cap (100–20,480 MB), oldest-first cleanup, and SHA-256 audit records. Recording construction alone does not start capture.
- Desktop agent agent/desktop_app.py: explicit MP4 start/stop checkbox (off by default) and Recording & Storage Settings dialog for duration, retained count, and storage cap. Agent mutex acquisition/release code was not changed.
- Tests: tests/test_session_recorder_settings.py covers off-by-default construction, bounded settings, retention cleanup, and symlink-safe deletion behavior. Existing fault-injection suite remains in tests/test_v2_fault_injection.py.
- Recording destination limitation: MP4 recordings are currently saved locally only. Community Library publishing remains disabled for video assets; the UI explicitly communicates this rather than implying an upload endpoint exists. Existing Community Library workflow JSON publishing is separate.
- Verification: GitHub source edits are committed on feature/v2-bidirectional-automation. No local laptop/desktop tools were used. Frontend build, Python tests, Windows packaged-agent validation, and live Render deployment must be confirmed by the branch CI/Render workflow before release.


- Backend backend/main.py: validates recording-control action and resource caps, enforces the existing authenticated non-read-only viewer and host-approval gates, relays recording status acknowledgements, and records start/stop request audit events.
- Security tests tests/test_recording_control_security.py: rejects community-upload mode, malformed actions, boolean-as-integer values, and out-of-range duration/retention/storage settings.

- Deployment routing check: render.yaml still configures the existing Render service to deploy from main. Pushing this feature branch does not trigger that service's auto-deploy; the Render service/Blueprint was not modified because switching its deployment branch would alter the active deployment target. No Render deployment is claimed.


## Mobile remote control recovery, privacy blackout, and viewport rotation — 2026-11-26
- Frontend `frontend/src/App.tsx`: expanded the draggable mobile action dock to expose Mouse Mode, Right-click, Scroll, Virtual Keyboard, Privacy, Clipboard Sync, File Transfer, Fullscreen, MP4 Start/Stop, V2 AI Workflow Replay, Recording Settings, and Disconnect. The dock routes actions through the established authenticated viewer WebSocket protocol; workflow replay is a host-local replay request and never uploads a workflow.
- Frontend viewport: added a ResizeObserver on the remote screen container plus resize/orientationchange listeners to reset zoom/pan on viewport changes. The CSS uses dynamic viewport units, orientation-specific sizing, safe-area-aware dock bounds, and a pitch-black remote screen background.
- Privacy overlay `agent/privacy_overlay.py`: retained the Win32 opaque layered surface with alpha 255 and made its SS_BLACKRECT window style explicit. Frontend privacy preview is solid `#000000`.
- Backend `backend/main.py`: allowlists the no-argument `workflow_replay` control event; viewer WebSocket control relay still requires a valid authenticated session, non-read-only role, host approval, and `validate_control`.
- Host `agent/host_agent.py`: receives workflow replay only over the authenticated, approved host WebSocket and replays the latest host-local workflow from the existing APPDATA workflow directory. The replay response is returned to the viewer as `workflow_replay_status`. Existing mutex and APPDATA paths are unchanged.
- Tests: `tests/test_input_dispatch.py` now asserts the replay event is accepted only without arbitrary path/payload fields; `test_instructions.json` includes the focused remote-control, session-security, and fault-injection command.
- Remaining verification: live browser automation is attempted against the supplied staging URL. Any browser-provider credit/availability failure is reported as not verified, never as a pass. GitHub Actions and Render status must be checked against the final pushed SHA.

- Follow-up UI detail: the same draggable dock is now displayed on desktop as well as mobile; the full-width desktop toolbar remains available. The dock uses a three-column desktop grid and touch-friendly mobile grid.


## Mobile floating controls and responsive viewer hardening — 2026-11-26
- `frontend/src/App.tsx`: corrected the dock's gated input shortcuts so Right-click and Scroll explicitly dispatch through the authenticated control WebSocket even when Mouse Mode was previously off, then enable Mouse Mode. Added distinct Scroll Up/Down actions, Virtual Keyboard focus-on-open, Workflow Steps and Community Library shortcuts, Zoom In/Out/Reset actions, and viewport-bounded dock dragging.
- `frontend/src/styles.css`: made the high-contrast dock persistently visible whenever a remote viewer session is active on both desktop and mobile; pinned it at z-index 9999 with safe-area-aware offsets, constrained the expanded grid to the dynamic viewport, and raised the mobile sidebar/drawer and overlay stacking order without covering the sidebar toggle.
- `tests/test_input_dispatch.py`: included host-local workflow replay in the accepted control protocol test cases.
- `tests/test_mobile_control_ui_contract.py`: added static contract tests for all dock actions, forced right-click/scroll dispatch, dynamic viewport/orientation observers, safe-area/z-index rules, and opaque black privacy styling.
- `test_instructions.json`: explicitly lists the mobile control UI contract and orientation/FAB stress regression commands in addition to the full Python test suite, frontend build, security scan, fault injection, and recording checks.
- Host privacy remains the native Win32 black rectangle (`SS_BLACKRECT`) at alpha 255. Recording remains manual start/stop with bounded local-only retention settings. Workflow JSON publish remains explicit opt-in from Workflow History; replay executes the latest host-local workflow only.
- Browser E2E still requires the deployed authenticated dashboard and an approved host. A blank host password cannot be used to verify remote input/blackout/recording against the real host.


## Final V2 UI, recording, CI and staging verification — 2026-11-26
- Branch head at verification: `35f167b3d383eb208a555693406be50cfc09a8fd` (`feature/v2-bidirectional-automation`). Source inspection confirms the mobile/desktop action dock, sidebar toggle, mouse/right-click/scroll, virtual keyboard dispatch, black privacy mode, clipboard/file transfer, zoom/fullscreen/disconnect, V2 workflow replay/history/community navigation, and manual recording settings/timer are present.
- GitHub Actions run [#87](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/actions/runs/45848238106): Python regression/unit suite PASS; frontend production build PASS; full-history Gitleaks PASS; Windows agent packaging and SHA-256 verification PASS. Optional live E2E job skipped because `RDP_BASE_URL` is not configured.
- `test_instructions.json` now contains directly executable shell command strings (not object records), addressing the Colab runner issue that attempted to execute `{ 'name': ..., 'command': ... }` as shell syntax. Includes dependency setup, compile, full regression suite, frontend build, mobile protocol/UI, recording/security, stress, fault injection, Gitleaks, and optional cloud E2E.
- Staging URL `https://remote-desk-pro-rtij.onrender.com`: authenticated registration/sign-in/sign-out succeeded using temporary test account `e2e_test_user_2026_01@example.com` (requested example address was already registered). Sidebar collapse/expand and workflow/community entry points were visible and working; no browser console or network errors were observed. The staging page displayed version `0.1.0` and did not expose a recording settings modal or active viewer control dock without an active host session. No host connection was attempted because the supplied host password was a placeholder. Therefore live viewer controls, pitch-black host blackout, remote keyboard/mouse, recording start/stop, and disconnect were NOT verified against a real host.
- Render routing remains intentionally unchanged: existing Render service `srv-dc0917utlv9c739h7o30` is configured to deploy from `main`; pushing this feature branch does not auto-deploy it. The separate `rtij` staging URL could not be mapped to a confirmed Render service because no Render workspace was selected. No Render deployment is claimed.
- `main` was not modified, merged, or deployed by this execution.

- `tests/e2e_cloud_headless.py`: refreshed the cloud relay E2E lifecycle assertions to verify recording is OFF after host approval, starts only after an explicit local recording command, stops on disconnect, and requires a fresh explicit start after reconnect. Privacy E2E now exercises `mode=black`; the synthetic host doubles expose the recorder lifecycle used by the production path.
- Responsive overflow follow-up: `frontend/src/styles.css` constrains root/layout/content/grid/panel widths to the available viewport while retaining dynamic viewport units for the dock and screen sizing. This addresses the browser's reported horizontal-scroll concern; exact 390×844 / 844×390 / 1440×900 measurements were not available from the browser run.

- The floating dock now labels Mouse Mode explicitly (ON · Trackpad + Tap / OFF), exposes a `Privacy ON · BLACK` active state via `aria-pressed`, and retains the live recording badge in the viewer header.

- Workflow History now parses a user-selected JSON export locally in the browser and displays a bounded preview of up to 100 step labels before any publish action. The dashboard exposes Recording & Storage Settings before a host session exists; the same modal remains available from the live viewer dock. This allows the settings UI and local workflow preview to be checked without pairing a host.

- Staging deployment verification: `https://remote-desk-pro-rtij.onrender.com` returned HTTP 200 from `/health` with PostgreSQL. The authenticated browser still rendered the older dashboard and did not expose the new pre-session Recording Settings button after the feature-branch push. The repository Render blueprint still specifies `branch: main`; no Render deployment target or `render.yaml` branch was changed to avoid altering the existing service. Feature-branch source/CI is verified separately from the live staging deployment.


## Main-to-V2 parity audit and privacy recording hardening — 2026-11-26

### Branch comparison
- Compared \`main\` (\`27802c6199e6706afe2f7aa4932ec74d0384f983\`) with \`feature/v2-bidirectional-automation\` (\`086c276b313c34b8baff985b22912fae322f0577\`) before this hardening pass. V2 was 95 commits ahead and 2 commits behind; the histories are intentionally divergent.
- The two main-only commits change the V2 workflow/manifest history and add a generated Windows executable under \`backend/downloads/\`. V2 already has its own feature-branch CI workflow and more complete V2 manifest; the generated binary is a build artifact, not source functionality, and was not copied into the source branch.
- No merge, rebase, cherry-pick, or write was made to \`main\`.

### Audited feature matrix
| Capability | V2 source state |
|---|---|
| V1 manual host consent | Preserved; manual approval remains the default |
| Trusted unattended PIN | Preserved: desktop toggle, 4–8 digit numeric PIN, server-side hash sync/verification, and host consent bypass only when enabled with a valid PIN |
| PIN storage | Hardened in this pass: desktop config now stores the PIN using Windows DPAPI (\`unattended_pin_enc\`) and restores it to the host process environment on startup; legacy plaintext config values are migrated on next save |
| V2 bidirectional control and workflow engine | Preserved; host-to-viewer resumable transfer, workflow replay/history/community publishing remain on V2 |
| Viewer control dock | Present on desktop and mobile with mouse mode, right-click, scroll up/down, virtual keyboard, black privacy, clipboard, file transfer, fullscreen, recording, workflow/community, zoom, and disconnect actions |
| Privacy blackout | Native host black overlay and solid black viewer preview are present |
| Recording | Manual start/stop remains available; this pass adds host-side MP4 auto-recording on successful privacy blank activation, finalization when privacy is disabled or the session ends, and a viewer disclosure badge. Manual recordings continue when privacy mode is disabled; a privacy-triggered recording cannot be manually stopped while the host remains blanked |
| Recording caps and retention | Existing max-duration, retention-count, storage-cap settings and SHA-256 audit log remain active |
| Responsive viewport | Dynamic viewport sizing, ResizeObserver, resize/orientationchange listeners, and safe-area-aware dock sizing are present |
| Keep / Download / Delete recording manager | Merged to `main` in PR #6; authenticated host recording list/delete/chunk-download controls, strict filename and symlink validation, bounded 256 KiB chunks, browser SHA-256 verification, post-stop saved prompt, manager drawer, and responsive styling. GitHub Actions code/security/Windows build checks passed; live authenticated host E2E and exact viewport measurements remain unverified |
| Exact live viewport/device E2E | Not verified. The public staging landing page was inspected signed out; no test account was created, no host was connected, and exact 390×844 / 844×390 / 1440×900 measurements were not captured |

### Verification boundary
- Added \`tests/test_privacy_recording_policy.py\` for privacy-start/stop semantics, manual-recording preservation, disclosure, and encrypted Trusted PIN persistence.
- \`test_instructions.json\` includes the focused privacy/recording/security test command in addition to the full regression suite, frontend build, and Gitleaks scan.
- The pre-hardening branch CI run #101 at \`086c276b\` passed Python regression, frontend build, full-history Gitleaks, and Windows executable packaging. Live cloud E2E was skipped because \`RDP_BASE_URL\` was not configured. A fresh CI run is required for the commits in this section.
- Public staging inspection at \`https://remote-desk-pro-rtij.onrender.com\` found the sign-in/create-account screen, title \`Remote Desk Pro\`, no visible version metadata, and no active session. The browser was left signed out. Browser Use was unavailable due to insufficient provider credits; the public TinyFish inspection succeeded.
- The staging login and real-host control path were not exercised. The Render deployment branch remains independently configured; no deployment or production environment change is claimed.


### Post-hardening CI and staging check
- Final code-and-test commit \`abd0ffff46081d4bd295e4b317f89160bf03ef6b\` passed GitHub Actions run [#111](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/actions/runs/45856782264): Python compile/regression suite PASS, frontend production build PASS, full-history Gitleaks PASS, Windows unified executable build and SHA-256 artifact verification PASS. Optional authenticated cloud E2E was skipped because \`RDP_BASE_URL\` is not configured.
- The subsequent public staging responsive inspection confirmed the sign-in card and all form controls fit in the available default viewport without observed clipping or overflow. The browser provider could not set exact 390×844, 844×390, and 1440×900 viewport sizes, so those exact dimensions remain unverified. Browser left signed out and no host session was started.
- Remaining release blockers: authenticated staging login/host E2E with a valid test account and connected test host; exact viewport-size measurements; and the Keep/Download/Delete MP4 recordings manager. No merge to \`main\` is authorized or performed.


### Recording manager implementation — 2026-11-26
- `agent/session_recorder.py`: added safe recording enumeration, audited deletion to `audit.jsonl`, bounded chunk reads (maximum 262144 bytes), strict basename validation, symlink rejection, and SHA-256 metadata.
- `agent/host_agent.py`: added approved-session dispatch for recording list, delete, and download-chunk requests; errors are returned without exposing filesystem paths.
- `backend/main.py`: added strict schemas for manager actions, retained the existing authenticated non-read-only viewer and approved-host gates, and relays only the manager response message types.
- `frontend/src/App.tsx` and `frontend/src/styles.css`: added the post-stop saved-recording prompt, manager controls in the viewer and floating dock, chunked download with browser SHA-256 verification, and responsive modal/banner styling.
- `tests/test_recording_control_security.py`: covers listing order/hash, symlink exclusion, audited deletion, traversal/invalid filenames, bounded chunk reads, and control schema rejection.
- Exact device viewport measurements and authenticated real-host E2E have not been run in this environment. Do not treat the manager as staging-verified until those checks are executed.


### V2 production cutover — 2026-11-26
- **Status:** PR #6 merged into `main`.
- **Cutover timestamp (UTC):** 2026-11-26T17:05:56Z
- **GitHub merge commit:** `98e7c0faf2a02a2234fe1600817e890fb13db27c`
- **Source feature commit:** `8889ac6d57115890098d8a2d57850b46c2cbac3f`
- **PR:** https://github.com/lokeshmakhijani1-debug/remote-desk-pro/pull/6
- **Pre-merge CI:** GitHub Actions run [#45864163987](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/actions/runs/45864163987) completed successfully on the exact source commit. Python regression/frontend build PASS; full-history Gitleaks PASS; Windows V2 executable build and checksum/artifact verification PASS. Optional public prerelease was skipped. The separate live cloud E2E step was skipped because `RDP_BASE_URL` is not configured.
- **Post-merge verification:** main-branch CI is expected to trigger on the merge and must be checked independently; do not infer its result from pre-merge checks.
- **Verification boundary:** authenticated staging login/host E2E and exact 390×844, 844×390, and 1440×900 viewport measurements have not been performed. Merge and CI do not constitute live deployment verification.


### V2 production verification follow-up — 2026-11-26
- Added `tests/test_v2_30_suite.py` for missing deterministic contracts: recording timer state, authenticated/approved recording WebSocket gates, storage-cap eviction order, saved-recording actions, recording modal responsive hooks, workflow scroll/shortcut capture, injected replay payload rejection, connection rate limiting, privacy emergency-unlock hotkey, floating dock action coverage, and bounded workflow stress.
- Added the dedicated suite command to `test_instructions.json`.
- Fixed `cleanup_recordings`: storage-cap eviction now removes oldest completed MP4 files first (the prior loop could remove the newest file when only the byte cap was exceeded); symlinks are excluded from retention candidates.
- Main CI and Windows Agent Build runs for the V2 merge completed successfully: [CI #45864759600](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/actions/runs/45864759600), [Windows Build #45864759383](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/actions/runs/45864759383), [CI #45864801375](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/actions/runs/45864801375). The dedicated matrix suite and storage-retention fix were subsequently validated by main CI [#45866748596](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/actions/runs/45866748596) on `223469524be9eb9779f3c2a280e1864e71343f1a` (backend pytest and frontend build passed); Windows Agent Build [#45866735128](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/actions/runs/45866735128) on `376de525c48c3b7ec8e4b9400104bda5449b6e0e` completed successfully. The workflow then committed the generated Windows binary and manifest to `main` at `68f97796ad237925cd456e4ca46df145343330c8`.
- Production `/health` and `/api/manifest` returned HTTP 200. The manifest does not expose a Git SHA. Production homepage inspection found a logged-out static login page with no viewport meta tag and no external JS/CSS assets; requested viewport sizes could not be set exactly, and authenticated recording-manager viewports remain unverified.
- The latest `latest-agent` release asset is present (68,502,584 bytes), SHA-256 `995f9c851dd7326fc8366d1774684afaee33639329075944dfcbed122b71bb54`. Windows workflow artifact digest: `ca7b13f0b31d1de7e60a420cb5b9d44858af0cec792872aa10063caaf2e540b0` (ZIP artifact digest, not the EXE digest).

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 376de525c48c3b7ec8e4b9400104bda5449b6e0e.
- EXE size: 68502584 bytes.
- EXE SHA-256: 995F9C851DD7326FC8366D1774684AFAEE33639329075944DFCBED122B71BB54.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: ed7725b6517b5ac03433a5eb9411ae9016ef80d0.
- EXE size: 68501567 bytes.
- EXE SHA-256: 436531D2E463BE54C094E4F95204ADCEAD3F5AC4DC9BA66CF1A958DCFF72EE06.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 137601c320bfe2c96dd221a435d0288659de58cc.
- EXE size: 68520501 bytes.
- EXE SHA-256: 8042C96FBB682E6E19A3FEE621F4F7BB0C09BC211A447632FE268A89C4D8DFCC.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


### V2 remaining-test remediation — 2026-11-26
- /api/manifest now exposes git_sha at the top level and under deployment, preferring RENDER_GIT_COMMIT, then GITHUB_SHA, with a source-prefix fallback.
- Backend static serving now resolves frontend/dist from the repository/image root and mounts Vite assets only when the built index.html exists. Dockerfile already builds and copies frontend/dist into /app/frontend/dist.
- frontend/index.html now includes the requested maximum-scale=5.0 and viewport-fit=cover viewport settings.
- Trusted PIN connect validation now accepts 4–8 digits, matching the stored PIN policy. Host unattended approval is extracted into approve_viewer_request; manual consent remains the fallback. Active recording start now uses start_recorder_once to reuse a live recorder through manual/privacy transitions.
- Expanded tests/test_v2_30_suite.py with real FFmpeg MP4 encode/decode lifecycle checks, manual/privacy recorder reuse, multi-chunk SHA-256 reassembly, max-duration stop and retention, 100/125/150% resolution mapping, public workflow publish/list/import/replay, Trusted PIN connect and consent bypass, endpoint-level invalid-PIN rate limiting, 200 host input events with rapid recording toggles, and manifest/static-serving contracts.
- Added tests/e2e_responsive_layout.mjs using Playwright and the built Vite CSS. It checks dock buttons and recording-manager layout at 390×844, 844×390, and 1440×900; CI installs Chromium and runs it after the frontend build.
- test_instructions.json includes the browser installation and layout test commands.
- Note: responsive Playwright coverage uses a DOM fixture styled by the production Vite CSS. It is not an authenticated real-host session test; production login and host-side workflows still require live E2E.
- Verified CI: [Remote Desk Pro CI #45870348035](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/actions/runs/45870348035) passed on source commit e0b1ef702032f4533973f8a3572b5ffe3db182f1 (138 passed, 1 skipped); frontend build and all three headless viewport cases passed.
- Verified Windows Agent Build: [#45870348072](https://github.com/lokeshmakhijani1-debug/remote-desk-pro/actions/runs/45870348072) succeeded on the same source commit.
- Render production /health and /api/manifest returned HTTP 200; manifest git_sha matched main HEAD 79805bd34a46fe34af0afb3dd2399af9c0e4c9f9. A cache-busted homepage response exposed the requested viewport-fit=cover metadata.
- The exact Vite JS/CSS build assets were fetched successfully from /assets/index-BZDfJSV8.js and /assets/index-CI2ZtAl5.css. The Windows agent is published as latest-agent with SHA-256 223DA23FA246E4741FB64E8E1085BE627E7C1693EF8C73EBA4449A0565B6E6D5.
- Playwright viewport coverage uses a DOM fixture styled by the production Vite CSS; authenticated live host-session E2E and physical Windows input/recording tests remain separate from this CI certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: bce710adae6aaa7bc1598d0bdfbdce43ddd66883.
- EXE size: 68502563 bytes.
- EXE SHA-256: A79682082641493C8A0C429AB091C46D5452EBE6938C6862BEC84938443A8B2C.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 36639060aabc15dbbf74919a8ee3b4189c2323b8.
- EXE size: 68520671 bytes.
- EXE SHA-256: C84E47E665EA036CFDACA086EC7542ED4F1EDE6C0F5FCFECEC8A073BFFFDECFC.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: e0b1ef702032f4533973f8a3572b5ffe3db182f1.
- EXE size: 68503682 bytes.
- EXE SHA-256: 223DA23FA246E4741FB64E8E1085BE627E7C1693EF8C73EBA4449A0565B6E6D5.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

 
## Production readiness, security and scale audit — 2026-11-26
- Added `docs/PRODUCTION_READINESS_AUDIT.md` with evidence-based status for all 30 requested failure vectors, security findings, limitations and NO-GO certification decision.
- Added `tests/test_production_scale_security.py`: deterministic 50-viewer Hub capacity, cross-user takeover/reconnect, stale-host cleanup, rate-limit threshold, clipboard/recording payload bounds and invalid control tests.
- Added dedicated test and SAST command entries to root `test_instructions.json` (pytest scale suite, pip-audit, Bandit).
- Baseline main at audit start: `da4a391a5bd49405455321bdffd7143cc9ffd8f6`. Existing CI run `45870931397` passed backend and frontend jobs before the audit-specific tests were added; new audit test execution must be confirmed from the subsequent Actions run.
- Production read-only probes returned HTTP 503 for both `/api/health` and `/api/manifest` during this audit. Treat live production availability as degraded/unverified until a fresh 200 response is recorded.
- Important gaps remain: process-local rate limiting, JWT revocation, password reset, account deletion, distributed WebSocket/resource limits, versioned DB migrations, and true 50+ concurrent live WebSocket / packet-loss / latency / disk-pressure / soak tests.
- No hostile authentication guessing, destructive file/recording operation, production load test, Render deployment or physical Windows host action was performed. Core streaming, input, Trusted PIN, privacy, MP4 and workflow code paths were not modified.
- Certification: NO-GO pending documented remediation and successful isolated load/fault-injection evidence.

- Follow-up read-only production probe recovered: `/api/health` and `/api/manifest` both returned HTTP 200; manifest git_sha matched inspected baseline `da4a391a5bd49405455321bdffd7143cc9ffd8f6`, database dialect `postgresql`, capacity target 50. First probe returned 503; recovered endpoint fetch latencies were ~4.6 s and ~4.4 s.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: e5b8d59ee188d48cbfd27dda72de9e6b661994c6.
- EXE size: 68520051 bytes.
- EXE SHA-256: 15977A980CFBE9CA7C5FFD8055A09F6335353E2D1B88772D3918722C92EB308F.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


## Phase 1–2 security audit update — 2026-11-27
- Transfer limits: frontend selection, backend relay, and endpoint receiver enforce a maximum file size of 50 MiB (52,428,800 bytes). Backend relay chunks are capped at 1 MiB; endpoint receiver chunk size is 64 KiB–2 MiB. No extension/MIME allowlist is enforced: arbitrary filenames/extensions are accepted after basename sanitization and subject to the host OS save flow.
- WebSocket hardening: inbound application text frames are now capped at 64 KiB and binary frames at 8 MiB before parsing/relay; JSON payloads must decode to an object before event dispatch. Device connection throttling now applies both per source IP and per source-IP/device pair.
- Regression coverage: `tests/test_websocket_security_bounds.py` asserts both frame limits and rejects non-string/non-bytes payload values.
- Known gaps not implemented/claimed as passing: password reset/recovery, OAuth/social login, account deletion/cascade, distributed rate limiting, TURN relay configuration validation and actual NAT fallback E2E, E2E media encryption, agent update signature verification, multi-monitor switching, audio sync, localization coverage, support/diagnostic export. Existing WebSocket relay uses TLS only when deployed behind correctly configured HTTPS/WSS termination; application-level E2E encryption is not evidenced.
- Security observations: auth tokens are HS256-signed and expiry-checked; password and Trusted PIN hashes use Argon2; login and device-connect routes use in-process IP throttles. Recording filename validation uses a strict `session_*.mp4` pattern and bounded chunk reads; symlink rejection is covered by existing tests. File transfer format allowlisting and malware scanning are absent.
- Audit scope: Phase 1 and Phase 2 source review only. Full SAST/dependency/secret scanners and test suites require GitHub Actions execution; no claim of 100% green until the workflow completes. Phase 3 load/stress testing intentionally deferred.


## Phase 3 — load, stress and fault-injection coverage (2026-11-27)
- Verified starting HEAD `bcacd8c3c3d9dd54ba1eda2a430655ed86fa759a`.
- CI run `45878916871` failed in the backend pytest step: 148 passed, 1 skipped, 1 failed. The failure was `test_t24_invalid_trusted_pin_is_rejected_and_connect_endpoint_rate_limits`: TestClient reused the same synthetic client address across tests, so prior attempts consumed the shared in-memory IP rate-limit budget before the test's eight expected 401 responses. Corrected test isolation by clearing only that test's synthetic IP/device counters; production throttling behavior was not relaxed.
- Added `tests/test_load_and_fault_injection.py`: 64 simultaneous viewer admission attempts against the configured 50-viewer cap; 32 concurrent 256 KiB resumable transfer streams; 50 MiB + 1 byte rejection at both transfer endpoints; truncated-chunk rejection and temporary-state cancellation; password-hash/account secret isolation; modifier-key and mouse-button release on disconnect; simulated 500 ms / 1 s / 2 s async latency; optional HTTPS live `/health` and response-header baseline check via `RDP_BASE_URL`.
- These are deterministic in-process tests. They do not constitute a real 50-client network load test, physical disk exhaustion test, actual recording encoder interruption test, or production remote-control session test. Those require isolated infrastructure and dedicated runner/device instrumentation.
- `test_instructions.json` now includes the load/fault suite and opt-in production health check command.
- GitHub Actions CI #318 on commit `5c443b94a0ede15466e3b91b48aa9818e133754e` completed successfully: backend `159 passed, 2 skipped`; frontend build and responsive-layout checks passed. The skipped tests include platform/live-environment checks; the optional live-health pytest remains opt-in.
- Core application runtime code was not modified in this phase; the only regression correction is test isolation. Screen relay, input control, Trusted PIN, privacy overlay, MP4 recording, transfer protocol, and workflow replay source paths remain unchanged.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 4e5789839cd87b7624acb8e2ce08957f88d4b153.
- EXE size: 68502136 bytes.
- EXE SHA-256: F41B74CFBA964248F42842D09FF8CB8AF7A48809EC84A56A564275779CA6FA2B.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


### Phase 3 verification outcome — 2026-11-27
- Verified CI run #318: backend 159 passed / 2 skipped; frontend production build and responsive layout checks passed. One Starlette/httpx deprecation warning remains non-failing.
- Regression fix: the initial account-isolation test used reserved `.test` email domains rejected by Pydantic EmailStr (422). Test fixture changed to `example.com`; no application authentication behavior was changed.
- Live production HTTPS health response body reported `status=ok`, `service=remote-desk-pro`, `database=postgresql`, and `capacity_target=50`. The HTTP content fetch did not expose response headers, so HSTS/CSP/frame/referrer header assertions remain unverified.
- Test coverage includes 64 concurrent Hub host registrations and 64 viewer admission attempts (50 admitted / 14 rejected), 32 parallel 256 KiB transfer streams, 32 concurrent secret-verification operations, wrong-email/cross-account/wrong-password login rejection, >50 MiB rejection, malformed/truncated chunks, simulated disk-full cancellation cleanup, disconnect key/button release, and 500 ms–2 s async latency delays.
- Limits: these are in-process Hub/storage/auth tests, not 64 real network WebSocket clients. Actual recording-encoder interruption, physical disk exhaustion, WAN packet loss, TURN/NAT traversal, and live remote-control E2E were not exercised. No destructive tests were run against production.
- Production certification is therefore **CI-green / live-health-body-green, but not fully certified** until security headers are verified and real network/recording/device load tests are run in an isolated environment.


## Windows agent build publication — Phase 3 final
- Windows Agent Build #153 completed build, release publication, binary commit, and workflow artifact upload from GitHub Actions.
- Build source recorded by the workflow: `37cbb7fea4aaa3e3a0d851996167fd7cdd985302`; application runtime code was unchanged in the later test/documentation commits.
- Current tracked binary: `backend/downloads/RemoteDeskPro-Agent.exe`; size `68,503,755` bytes; SHA-256 `A4EE5CD70FDBB4D4FF957A08BC20C281EDC0D69068C4ED68D3F5EA85742C2070`.
- Machine-readable metadata: `backend/downloads/agent-build.json`.
- Publishing commit: `bea186d3ef33297211beb4e89c1d6999854d9bd3`.
- Windows publishing now commits the binary and separate build metadata, then explicitly checks fetch/rebase/push results and retries concurrent fast-forward races. It no longer appends to this shared manifest during the binary push.
- Build success confirms packaging and release upload only; it does not certify live Windows input, recording, file-transfer or device E2E behavior.


## Phase 4/4 production certification hardening — 2026-11-27
- `backend/main.py`: centralized HTTP security-header middleware (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, CSP framing/object/base directives, conditional HSTS).
- `tests/test_security_headers.py`: verifies headers on responses and HSTS scheme/proxy behavior.
- `scripts/verify_websocket_stress.py`: Uvicorn-backed real TCP loopback host/viewer concurrency, jitter, binary relay, abrupt disconnect, memory and FD leak checks against temporary SQLite.
- `scripts/verify_windows_e2e.py`: SHA-256 and byte-size verification against published agent metadata; optional Windows-only launch is gated behind `--execute`.
- `tests/test_windows_e2e_harness.py`: verifies successful checksum validation, rejects tampered binaries and malformed metadata before launch, and mocks successful launch behavior.
- `.github/workflows/ci.yml`: separate network-stress and security jobs for pip-audit, Bandit high-severity findings, and full-history Gitleaks.
- `test_instructions.json`: reproducible commands for dependency, regression, network stress, security scans, and opt-in Windows E2E.
- Limitations: the automated loopback test is not a substitute for geographically distributed WAN/TURN/NAT testing. The Windows GUI harness was added but not executed against a physical Windows desktop in this cloud-only run. No destructive production testing or database writes were performed.

- Follow-up hardening: HSTS is enabled only when the ASGI scheme is HTTPS; arbitrary client-supplied forwarding headers cannot enable it. Gitleaks CI uses `GITLEAKS_LOG_OPTS=--all` to scan all available Git refs/history.

- Gitleaks CI: Gitleaks Action scans the pushed commit and a separate pinned Gitleaks 8.24.3 CLI step scans all refs/history with `--log-opts=--all`. The Windows GUI launch is an opt-in platform-specific command and is not run by the generic non-interactive test command list.


## Session recording → workflow pipeline — 2026-11-27
- Host MP4 recordings capture a companion `.events.jsonl` sidecar containing replay-safe mouse-down, scroll, modifier/navigation key, and Ctrl+A clear-input events with elapsed-time offsets. Printable keystrokes, typed text, clipboard content, passwords, and arbitrary WebSocket messages are excluded.
- `agent/workflow_engine.py` converts a completed MP4 plus its matching event sidecar into the existing schema-v1 normalized JSON workflow format. MP4-only historical recordings are explicitly rejected because video pixels do not establish reliable input semantics.
- The host agent exposes an approved-session conversion request and streams the generated JSON to the viewer in bounded WebSocket chunks. Backend relay allowlists and validates conversion requests, export IDs, filenames, payload sizes, and chunk sizes before forwarding.
- Added owner-scoped `rdp_saved_workflows` persistence, authenticated create/list/delete endpoints, explicit publish/unpublish endpoints, source-recording metadata, and a Supabase migration with owner-scoped RLS policies and a 2 MB payload constraint. Public copies continue to use the existing community workflow table and import flow.
- Workflow History UI saves local JSON privately, lists saved workflows, and supports explicit publish, unpublish, and delete. Host Recordings exposes conversion only when an event sidecar exists.
- Replay remains on the existing host-side `WorkflowReplayEngine`; converted files use its schema and support a simulated repeat-execution test. Conversion and publishing never execute a workflow automatically.
- Added tests for sidecar privacy, MP4/event conversion, video-only rejection, replay-engine repeat execution, owner isolation, publish/unpublish/delete, sensitive-field rejection, and relay frame validation.
- CI commands are listed in root `test_instructions.json`. Simulated cloud replay tests do not represent physical Windows input execution certification.


## Feature branch delivery manifest — session recording workflow pipeline
**Branch:** `feature/v2-bidirectional-automation`  
**Current head:** Follow the live GitHub branch reference; this manifest intentionally avoids a stale pinned SHA.  
**Deployment:** feature-branch only; not merged to `main`, and the Supabase migration has not been applied to the live project.
**Verification snapshot:** workflow pipeline, frontend build, WebSocket stress, fault-injection/load tests, Gitleaks, and Windows packaging passed in GitHub Actions. Full legacy suite still has three unrelated privacy-overlay failures.

| File / endpoint | Responsibility | Verification | Release status |
|---|---|---|---|
| `agent/session_recorder.py` | Writes MP4 companion `.events.jsonl` with elapsed-time offsets and replay-safe mouse/scroll/navigation/modifier events; excludes printable text and clipboard | Sidecar privacy tests; retention/delete lifecycle | Committed to feature branch |
| `agent/workflow_engine.py` | Converts completed MP4 + matching event sidecar to schema-v1 workflow JSON; requires safe focus coordinates; output is accepted by existing replay engine | Converter validation and repeated simulated replay test | Committed to feature branch |
| `agent/host_agent.py` | Captures approved control events during recording; handles recording-conversion requests; exports JSON in bounded chunks | Python compile + host workflow tests + relay transport tests | Committed to feature branch |
| `backend/main.py` | Authenticated workflow save/list/delete/publish/unpublish APIs; private/public payload validation; strict WebSocket conversion/export allowlists | Owner-isolation/API lifecycle and relay frame tests | Committed to feature branch |
| `backend/database.py` | Adds owner-scoped `SavedWorkflow` model | SQLite metadata/API integration tests | Committed to feature branch |
| `supabase/migrations/20261127120000_saved_workflows.sql` | Creates `rdp_saved_workflows`, owner RLS policies, metadata indexes and 2 MB payload bound | Migration source reviewed; apply to target Supabase project still pending | Committed; not applied to production |
| `frontend/src/App.tsx` | Recording conversion action; private workflow library; explicit publish/unpublish/delete; replay-latest-on-host action | Workflow UI contract tests + Vite build | Committed to feature branch |
| `frontend/src/api.ts` | Adds method-aware authenticated API helper for DELETE and POST operations | Frontend build | Committed to feature branch |
| `tests/test_session_workflow_conversion.py` | Sidecar sanitization, conversion, video-only rejection, invalid timeline/focus rejection, repeat replay simulation | Dedicated pipeline CI job | Committed to feature branch |
| `tests/test_saved_workflows.py` | Owner isolation, save/list/delete, publish/unpublish, sensitive-field and printable-key rejection | Dedicated pipeline CI job | Committed to feature branch |
| `tests/test_workflow_transport_security.py` | Validates conversion request and bounded/correlated export frames | Dedicated pipeline CI job | Committed to feature branch |
| `tests/test_workflow_ui_contract.py` | Confirms management, conversion, export and replay controls exist | Dedicated pipeline CI job | Committed to feature branch |
| `.github/workflows/test-and-build-v2.yml` | Adds an independent pipeline job for workflow tests, frontend build, WebSocket stress and fault injection | GitHub Actions | Committed to feature branch |

### Workflow API contract
| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/api/workflows` | Authenticated owner | Save a validated workflow privately with metadata |
| GET | `/api/workflows` | Authenticated owner | List the caller's workflows |
| DELETE | `/api/workflows/{workflow_id}` | Owner only | Delete private workflow and its linked public copy |
| POST | `/api/workflows/{workflow_id}/publish` | Owner only + explicit action | Publish a validated copy to Community Library |
| POST | `/api/workflows/{workflow_id}/unpublish` | Owner only | Remove public copy and return to private state |

### Recording conversion contract
- Viewer sends `recording_convert_workflow` only over an approved live session.
- Host accepts only a basename matching the recording filename pattern and requires a finalized MP4 with a non-symlink event sidecar.
- Host emits `workflow_export_start`, ordered `workflow_export_chunk` frames, and `workflow_export_end`; backend validates frame IDs, filenames, lengths and payload bounds.
- Viewer verifies the reassembled UTF-8 byte count before saving the JSON to the authenticated private library.
- Conversion does not run the workflow. The operator must explicitly click **Replay Latest on Host**; replay executes on the approved host using `WorkflowReplayEngine`.
- Video-only historical recordings cannot be converted reliably. No MP4 or event-sidecar assets were found in the repository tree; recordings stored under the host's local AppData folder are not accessible through GitHub repository operations.

## Supabase saved-workflows RLS remediation checkpoint — 2026-11-27

- Scope: Supabase project `Remote-desktop-pro` (`qxssuczpumsaqywifirv`), table `public.rdp_saved_workflows` only; repository branch `feature/v2-bidirectional-automation`.
- Live schema inspection: `id INTEGER`, `owner_id INTEGER NOT NULL` referencing `public.rdp_users(id)`, `name VARCHAR(120)`, `description VARCHAR(1000)`, `tags JSON`, `workflow JSON`, nullable `source_recording VARCHAR(255)`, nullable `community_workflow_id INTEGER`, `is_public BOOLEAN`, and `created_at/updated_at TIMESTAMP WITHOUT TIME ZONE`. Live table contains zero rows.
- Live security state at inspection: RLS disabled; no policies. This was a critical exposure to Supabase Data API roles. Existing explicit table grants to `anon` and `authenticated` include non-DML privileges; no row-level protection existed.
- Migration `supabase/migrations/20261127120000_saved_workflows.sql` currently defines JSONB columns and timestamptz columns, while the live table uses JSON and timestamp without time zone. Because it uses `CREATE TABLE IF NOT EXISTS`, it does not reconcile those existing type differences.
- Identity verification: Remote Desk Pro's FastAPI issues custom HS256 tokens signed with `APP_SECRET_KEY`; the token `sub` is the numeric `rdp_users.id` serialized as text. Supabase Auth currently contains zero users. Supabase Auth JWT `sub` is UUID-based and is not the same claim context as the application's custom FastAPI token.
- The migration's current `(auth.jwt() ->> 'sub')::integer` policy predicate is therefore not validated for Supabase Auth and must not be applied as-is. No trusted Supabase-Auth-UUID-to-`rdp_users.id` mapping or server-controlled `app_metadata` claim exists in this project.
- **Production SQL status: NOT APPLIED.** RLS remains disabled; no policy or grant changes were made. This is intentionally blocked rather than installing an owner policy that can cast a UUID or authorize the wrong identity.
- **Migration alignment status: BLOCKED.** The migration was not rewritten or applied because the correct authorization bridge is not present. Next prerequisite: define and implement a trusted identity mapping (for example, a Supabase Custom Access Token Hook issuing a server-controlled `app_metadata.rdp_user_id` claim after linking an Auth UUID to an active `rdp_users.id`), then validate owner-scoped CRUD policies against that claim and reconcile the existing live column types.
- Windows physical-host tests were not run in this session; local validation remains pending. No secrets were read or written.
- Branch guard: this checkpoint is recorded only on `feature/v2-bidirectional-automation`; `main` was not modified.


## Supabase saved-workflows RLS lock — verified execution update (2026-11-27)

- Scope remains strictly limited to Supabase project `Remote-desktop-pro` (`qxssuczpumsaqywifirv`) and `public.rdp_saved_workflows`.
- **Access-path audit: PASS.** Feature-branch `frontend/src/App.tsx` uses authenticated FastAPI `/api/workflows` endpoints; `frontend/src/api.ts` is a browser `fetch()` wrapper and contains no Supabase/PostgREST client; `frontend/package.json` has no Supabase client dependency. `agent/host_agent.py` records/converts/replays host-local workflows over the approved WebSocket session and contains no Supabase/PostgREST access. `backend/main.py` uses SQLAlchemy `SavedWorkflow` ORM queries for CRUD. No direct frontend or agent PostgREST calls to this table were found in the inspected feature-branch source.
- **Backend role verification: PASS.** Live database connection role and table owner are both `postgres`; `rolbypassrls=true`. The backend's SQLAlchemy `DATABASE_URL` connection therefore retains server-side access when RLS is enabled. No connection secret was read or recorded.
- **Production RLS: APPLIED.** Executed exactly `ALTER TABLE public.rdp_saved_workflows ENABLE ROW LEVEL SECURITY;` successfully. Post-change verification confirms `relrowsecurity=true`, no policies, and no SELECT/INSERT/UPDATE/DELETE table grants for `anon` or `authenticated`. Existing non-DML grants are unchanged. No permissive public policies were created.
- **Data API posture:** `anon` and `authenticated` have no DML grants and no RLS policies on this table. They cannot read or mutate saved workflows through PostgREST. Backend `postgres` remains able to use SQLAlchemy.
- **Migration aligned:** `supabase/migrations/20261127120000_saved_workflows.sql` retains table/index creation and enables RLS, but deliberately defines no owner policies based on the custom FastAPI JWT. This migration's RLS lock matches the verified production access boundary. It does not reconcile pre-existing live column-type differences; those remain documented and require a separate schema-alignment decision.
- **No policy bridge implied:** FastAPI custom HS256 tokens are not Supabase Auth JWTs. Owner authorization remains enforced in authenticated FastAPI routes; no attempt is made to consume the FastAPI token via `auth.jwt()`.
- **Physical Windows tests:** not executed in this session; pending local host validation. Existing local repo path was not accessible to this cloud execution environment; changes were applied through the GitHub API directly to the specified feature branch.
- **Branch guard:** migration and manifest changes are confined to `feature/v2-bidirectional-automation`; `main` was not targeted.


## Saved-workflows TRUNCATE privilege remediation — 2026-11-27

- Scope: project `Remote-desktop-pro` (`qxssuczpumsaqywifirv`), table `public.rdp_saved_workflows` only; branch `feature/v2-bidirectional-automation`.
- **Production SQL applied:** `REVOKE TRUNCATE ON TABLE public.rdp_saved_workflows FROM anon, authenticated;` completed successfully.
- **Migration aligned:** `supabase/migrations/20261127120000_saved_workflows.sql` now includes the same targeted REVOKE immediately after enabling RLS. No other table privileges or tables are modified by this statement.
- RLS remains enabled with no policies. Previously verified SELECT/INSERT/UPDATE/DELETE grants remain absent for `anon` and `authenticated`; this update additionally removes their TRUNCATE privilege. The verified backend `postgres` role has `BYPASSRLS` and retains its server-side SQLAlchemy access.
- Verification is recorded separately after re-reading effective table privileges and RLS state. Windows physical-host tests remain pending; no local test pass is claimed.
- This checkpoint supersedes any earlier manifest wording that said the RLS change or migration alignment was pending. The separate live-schema type mismatch remains unresolved and is not altered here.
- Branch scope: feature branch only; `main` was not modified.


## Global privacy emergency unlock hardening — 2026-11-27

**Branch:** `feature/v2-bidirectional-automation`  
**Implementation scope:** `agent/privacy_overlay.py`; no production API, network port, or Render service configuration changed.  
**Global shortcut:** Windows `Ctrl+Alt+Shift+U` (`RegisterHotKey` ID `0x5244`, modifiers Control + Alt + Shift).  
**Overlay behavior:** Existing visible tkinter overlay and local key bindings are retained. The global listener runs on a dedicated Win32 message thread so it works when the overlay does not own keyboard focus. A received `WM_HOTKEY` sets the stop event, invokes the normal unlock callback, and requests overlay teardown. Registered hotkeys are unregistered in the listener's `finally` cleanup path. Registration, message APIs, focus, display-affinity, and tkinter startup are exception-guarded; non-Windows platforms do not attempt Win32 registration.

| File / suite / service | Change or responsibility | Verification / result | Status |
|---|---|---|---|
| `agent/privacy_overlay.py` | Adds `_stop_flag`, isolated Windows global-hotkey message thread, `RegisterHotKey`, `WM_HOTKEY` dispatch, stop signaling, and `UnregisterHotKey`; preserves tkinter overlay and `PrivacyOverlayManager` alias | Source contract reviewed against `test_t25_privacy_overlay_registers_emergency_unlock_hotkey`; automated execution delegated to GitHub Actions | Committed to feature branch |
| `tests/test_v2_30_suite.py::test_t25_privacy_overlay_registers_emergency_unlock_hotkey` | Static contract for registration, message dispatch, stop event, and unregistration | Added to focused regression command; CI pending at manifest creation | CI pending |
| `tests/test_input_dispatch.py` | Existing mouse, keyboard, clipboard paste, text input, and input-release regression suite | Inspected; included in focused regression command | CI pending |
| `tests/test_session_workflow_conversion.py` | Session recording to workflow conversion and replay compatibility | Included in focused regression command | CI pending |
| `tests/test_saved_workflows.py` | Saved-workflow persistence and owner-isolation tests | Included in focused regression command | CI pending |
| `tests/test_v2_workflow_engine.py` | V2 workflow engine regression suite | Included in focused regression command | CI pending |
| `tests/test_adaptive_replay_10_envs.py` | Adaptive replay environment regression suite | Included in focused regression command | CI pending |
| `test_instructions.json` | Adds one non-interactive command covering T25 and the six requested suites | JSON parsed before update; command committed | Committed to feature branch |
| `PROJECT_MANIFEST.md` | Records changed files, test scope, endpoint/service impact, and verification state | This section | Updated on feature branch |
| Windows global hotkey / tkinter overlay | Local desktop OS message registration and visible overlay | No HTTP endpoint, listening port, or cloud service added/changed; physical Windows interaction not yet certified | CI / physical-host verification pending |

### Focused regression command

```bash
python -m pytest -q tests/test_v2_30_suite.py::test_t25_privacy_overlay_registers_emergency_unlock_hotkey tests/test_input_dispatch.py tests/test_session_workflow_conversion.py tests/test_saved_workflows.py tests/test_v2_workflow_engine.py tests/test_adaptive_replay_10_envs.py
```

### Commit and CI checkpoint
- Implementation commits: `6200274d8cf925f12218a03ec33707d1731c503a` and `d09f16806d5635efede7323b25d34183275f2238`.
- Regression-instruction commit: `c4f8e56f47806ffc1ceff066cc64e06514f8dce5`.
- GitHub Actions workflow `.github/workflows/test-and-build-v2.yml`, run `46035984350` (run #163), was observed pending at manifest creation. No local `.venv` or physical Windows desktop test was executed through GitHub's file API.
- `main` remained at `826ac493df37314b1ee25a6c104e18b91c795e82` during these feature-branch commits.
- No deployment, Supabase schema, production data, service configuration, or network endpoint was modified.


## Privacy overlay follow-up — latest source and CI checkpoint (2026-11-27)

- Final implementation follow-ups: `07ee2984184c7e94e647c0cc1eaf04433250fcc5` retains the native `SS_BLACKRECT = 0x00000004` opaque-black style contract; `fc29e0f98e9ae7e700017f36338b6abd46599e0a` makes startup report `False` if tkinter cannot initialize or become ready. The global listener remains best-effort and exception-safe.
- CI run #161 (`46035949142`, implementation commit `6200274d8cf925f12218a03ec33707d1731c503a`): Python compilation passed; regression suite reported 175 passed, 3 failed, 2 skipped. Failures were the missing layered-alpha source contract, missing `os` module/platform guard, and missing exact RegisterHotKey source contract. These were corrected in subsequent commits.
- CI run #166 (`46036199390`, commit `e2219853bb840fe1b8647ff031174ecddd99fe87`): Python compilation passed; regression suite reported 177 passed, 1 failed, 2 skipped. The sole remaining failure was the `SS_BLACKRECT` source contract; the constant was added in `07ee2984184c7e94e647c0cc1eaf04433250fcc5`.
- Latest branch source includes all listed fixes. GitHub Actions run #168 (`46036633589`, commit `fc29e0f98e9ae7e700017f36338b6abd46599e0a`) was queued/pending at this checkpoint; it is the validation run for the latest code. The run #166 Windows packaging job was still in progress, so final Windows packaging status is not inferred from the Python job.
- The six requested suites all exist on the branch and are listed together with T25 in root `test_instructions.json`. The workflow's all-tests command also includes them. No local `.venv` execution was possible or claimed; CI used GitHub-hosted Python 3.12.
- Physical Windows shortcut behavior, focus-independent hotkey delivery, and teardown remain pending a Windows desktop test. Ubuntu CI verifies source contracts and non-Windows safety only.
- Latest feature branch commit before this manifest update: `fc29e0f98e9ae7e700017f36338b6abd46599e0a`. `main` remained `826ac493df37314b1ee25a6c104e18b91c795e82`; no production service, endpoint, database, or deployment was changed.


## V2 staging deployment verification — 2026-11-27
- Workspace: `My Workspace` (`tea-dau2kcrncjis73agt6bg`).
- Service: `remote-desk-pro` / `srv-dc42jh49v7es73dmas70`; plan **Free**, region **Singapore**, Docker runtime, repository `lokeshmakhijani1-debug/remote-desk-pro`, tracked branch `feature/v2-bidirectional-automation`.
- Public V2 URL: https://remote-desk-pro-rtij.onrender.com
- Latest verified deployment before this manifest-only update: `dep-dc4r8n29lscs73enou6g`, status **live**, commit `a19a14e14b434a2b3fbaf739c5d172307d988fda`.
- Live HTTP checks: `GET /api/health` returned HTTP 200 with `status=ok` and `database=postgresql`; `GET /api/manifest` returned HTTP 200 and reported `git_sha=a19a14e14b434a2b3fbaf739c5d172307d988fda`, V2 feature flags including workflows, clipboard, file transfer, recording and privacy banner.
- Root page loaded and rendered the Remote Desk Pro sign-in screen. No authenticated workflow CRUD, device pairing, host/viewer WebSocket session, or physical Windows agent session was exercised.
- Dockerfile sets `PORT=10000`, exposes port `10000`, and starts Uvicorn on `0.0.0.0:10000`.
- Render service metadata currently reports an empty Render-side `healthCheckPath`; the application endpoint itself is healthy, but the dashboard setting `/api/health` was not changed because the available Render service API does not expose that field and the browser-control service was unavailable. This is recorded as a configuration follow-up, not misreported as configured.
- The staging service is already connected to PostgreSQL (verified by its live health payload). Render's available service detail response does not expose environment-variable values or a safe variable-copy operation, so secret-bearing variables were not read, printed, or copied. Production env settings were not touched.
- Production isolation verified from Render workspace inventory: `srv-dc0917utlv9c739h7o30` still tracks `main`; its URL is `https://remote-desk-pro-pj29.onrender.com`. No action was taken on that service. GitHub `main` remains outside this deployment workflow.


## Host Offline reliability remediation — 2026-11-27

- **Branch:** `feature/v2-bidirectional-automation` only. `main` and the production Render service remain untouched.
- **Root-cause finding:** the host agent used WebSocket protocol keepalive values of a 5-second ping interval and 5-second ping timeout. A short WAN/proxy/event-loop stall could therefore close an otherwise recoverable host socket. The backend immediately removed the current host socket, broadcast `host_offline`, and persisted `Device.online=false`; the agent then reconnected with exponential backoff. This creates avoidable Host Offline transitions during transient network jitter.
- **Host liveness protocol:** the agent now sends an authenticated application-level `host_heartbeat` every 15 seconds on its existing authenticated host WebSocket. The signaling server acknowledges it with `host_heartbeat_ack` and applies a 45-second receive inactivity timeout so a dead socket is eventually removed rather than left online indefinitely.
- **Transport resilience:** WebSocket protocol ping interval is increased to 20 seconds and ping timeout to 30 seconds. Existing bounded reconnect backoff and host identity checks remain unchanged.
- **Ports/services/packages:** no new listening ports, background services, external packages, TURN credentials, OAuth keys, or environment variables. Existing Render Docker service and port binding remain unchanged. No `.env` values were read or changed.
- **Modified/created files:** `agent/host_agent.py` (heartbeat sender and tolerant transport keepalive); `backend/main.py` (heartbeat acknowledgement and 45-second receive deadline); `tests/test_host_presence_heartbeat.py` (heartbeat contract and acknowledgement tests); `test_instructions.json` (focused liveness/fault regression command); `PROJECT_MANIFEST.md` (this record).
- **Verification boundary:** source-level changes and deterministic unit tests are committed to V2; GitHub Actions and the isolated V2 staging deploy must pass before claiming runtime verification. Physical Windows host reconnection cannot be verified while the registered Desktop Commander machine is offline. Production deployment is explicitly excluded.


## V2 Windows staging host certification — 2026-11-27
- Added `.github/workflows/windows-staging-host-e2e.yml`: Windows `windows-latest` workflow, manually dispatchable against the dedicated V2 staging URL; downloads the previously built `RemoteDeskPro-Agent-Windows` artifact from Actions run `46046835808`, records its executable SHA-256, rebuilds the current feature-branch agent, runs the packaged EXE, and uploads JSON evidence plus the rebuilt executable.
- Added `tests/windows_staging_host_e2e.ps1`: registers a unique temporary staging account/device, starts the packaged EXE in headless host mode, verifies online registration, observes at least two logged heartbeat acknowledgements at the 15-second cadence, applies a process-scoped outbound TCP/443 firewall interruption, verifies offline transition and reconnect, then terminates the EXE and verifies the final offline transition.
- Modified `agent/host_agent.py`: logs server heartbeat acknowledgements so the Windows runner can verify the 15-second heartbeat protocol from the packaged process.
- Existing packages reused; no new runtime package was added. Windows build uses the existing `agent/requirements.txt` and `agent/build_windows.ps1` (Python 3.12 / PyInstaller).
- Ports: staging HTTPS/WSS outbound TCP 443; Render application container port remains 10000 (unchanged). No new listening port.
- Evidence workflow artifact: `windows-staging-host-e2e-evidence`; JSON report path: `tests/artifacts/windows_staging_host_e2e.json`.
- Side-effect boundary: the current API has no safe device/account deletion endpoint. The harness creates a uniquely named test account and paired device and leaves the device offline after the run; no database deletion or cleanup endpoint is attempted. Run only against the dedicated V2 staging database.
- Execution status at commit time: workflow and harness committed; cloud Windows execution still pending. A successful build artifact alone is not a 100% V2 certification.
- External Vercel check: commit status reports a failed Vercel deployment link (`3moujcCRj1r2Me9iKxA5YT1VVo4X`). Its detailed deployment log is not accessible through the connected GitHub interface; no speculative Vercel config change was made.


## Universal QA and security audit workflow — 2026-11-27

- Added `.github/workflows/universal-qa-audit.yml`, a repository-agnostic GitHub Actions workflow with `workflow_dispatch` and all-branch push triggers. It does not contain Remote Desk Pro service names, fixed deployment URLs, project secrets, or project-specific assumptions.
- Technology detection records whether Python dependency manifests, Node package manifests, and Dockerfiles are present. Gitleaks scans Git history; Semgrep runs generic SAST rules; pip-audit checks discovered `requirements*.txt` files; npm audit checks Node projects only when a lockfile is present.
- Optional live checks accept a workflow-dispatch `base_url` or repository variable `QA_BASE_URL`. Playwright performs a generic same-origin crawl (up to 20 pages), captures page titles/statuses and JavaScript page errors; OWASP ZAP runs its baseline scan against the supplied target only. No live target is contacted when no URL is configured.
- Reports are consolidated into `reports/universal-qa/audit-report.json` and `audit-report.md`, with individual scanner evidence uploaded as the `universal-qa-audit-reports` Actions artifact (30-day retention).
- Scanner failures are non-blocking by default so the report can be generated; manual dispatch can enable `fail_on_findings` for a strict gate. Findings must be reviewed in scanner evidence; a baseline scan is not a penetration-test certification.
- Existing tools/actions reused: GitHub-hosted Ubuntu runner, Gitleaks Action, Semgrep, pip-audit, npm audit, Playwright Chromium, OWASP ZAP stable container, and upload-artifact. No application runtime dependency, listening port, Render service, deployment, database, or environment secret was added or changed. Optional target configuration uses only `QA_BASE_URL`.
- Updated root `test_instructions.json` with SAST/dependency, JSON validation, YAML lint, and manual cloud-artifact review instructions.
- Scope: this workflow and documentation were committed only to `feature/v2-bidirectional-automation`; `main` and production Render remain untouched. The first cloud workflow run and its scanner findings are pending Phase 4.


## Universal Lighthouse and UI/UX audit extension — 2026-11-27

- Extended `.github/workflows/universal-qa-audit.yml` with optional Lighthouse CLI collection for performance, accessibility, best-practices and SEO categories. JSON and HTML outputs are retained with the universal QA artifact.
- Added rendered-page DOM/CSS inspection using the already-installed Playwright Chromium browser. It records page title, viewport metadata, heading and landmark counts, image alternative-text coverage, accessible names for buttons/links/form fields, sampled text contrast, horizontal overflow, stylesheet count, inline style count, font-family samples, and body font size.
- Added a reproducible UI/UX heuristic score out of 100 with explicit metric penalties and a full-page screenshot. The score is a triage heuristic only; it is not a WCAG conformance result, accessibility certification, human usability study, or visual-design judgment.
- The report includes three evidence-guided styling directions: Accessible clarity, Responsive minimalism, and Action-focused product UI. They are recommendations for review, not automatic CSS edits.
- Additional evidence: `reports/universal-qa/lighthouse.report.json`, `lighthouse.report.html` (Lighthouse CLI output), `uiux-audit.json`, `uiux-audit.md`, and `uiux-homepage.png`, subject to target availability and successful execution.
- No new application runtime dependency, server, listening port, environment secret, Render deployment, database change, or production request was introduced by the code change. The audit uses runner-installed Lighthouse and the existing optional `base_url`/`QA_BASE_URL` target.
- Updated `test_instructions.json` with YAML/JSON validation and instructions to inspect the Lighthouse and UI/UX evidence artifact.
- Scope remains the V2 feature branch only. No changes to `main` or production Render. Actual Lighthouse scores, DOM metrics, screenshot evidence, and scanner execution are pending the dedicated Phase 4 workflow run.


## V2 staging execution adapter — 2026-11-27

- Added `.github/workflows/v2-staging-universal-qa.yml`, a narrow caller workflow that invokes the reusable universal audit with the V2 staging base URL. It is limited to the V2 feature branch and relevant workflow/application paths; the generic workflow itself remains project-agnostic.
- Extended `.github/workflows/universal-qa-audit.yml` with `workflow_call` inputs for `base_url` and `fail_on_findings`, allowing other repositories/workflows to reuse it without copying scanner steps.
- Triggered by a feature-branch push. Staging execution run: `46049417804` (GitHub Actions). It runs Gitleaks, Semgrep, Python/Node dependency checks, Playwright, OWASP ZAP, Lighthouse, DOM/CSS inspection, and artifact/report publication.
- Run observation at documentation update: Gitleaks, Semgrep, Python dependency audit, Node dependency audit, and Playwright smoke/crawl completed successfully; ZAP baseline was still running. Lighthouse, DOM/CSS UI/UX inspection, consolidated artifact publication, and final run conclusion were not yet available. Do not treat Phase 4 as complete until run `46049417804` finishes and its evidence artifact is inspected.
- No application code, database, Render service configuration, secrets, or production deployment was changed. The staging URL is supplied by the V2-specific caller; the universal audit remains reusable and configurable.


### Phase 4 runner hardening

- Fixed audit concurrency isolation to include the workflow name and branch. This prevents the universal push workflow and the V2 staging caller from cancelling each other when they run concurrently.
- The first staging run (`46049417804`) was cancelled during ZAP after concurrent feature-branch documentation pushes triggered the generic push workflow; it did not produce Lighthouse or DOM/CSS results. The Gitleaks, Semgrep, Python dependency, Node dependency and Playwright steps had passed before cancellation.
- Corrected Lighthouse Chrome discovery to use the executable path exposed by the installed Playwright Chromium browser, rather than assuming a system-wide Chrome binary exists on the runner.
- Bounded the ZAP spider to five minutes and the container invocation to twelve minutes so a target crawl cannot occupy the job indefinitely.
- A new staging run is triggered by the workflow hardening commit; its result and report artifact remain pending.


## 2026-11-28 — Phase 2 Security Remediation (V2 feature branch)

- Hardened HTTP security headers with an explicit CSP: same-origin scripts, form-action and frame restrictions, explicit resource directives, deployment-aware API/WebSocket connect origins, and a separate inline-style-attribute policy for existing React styles.
- Added Cross-Origin-Embedder-Policy, Cross-Origin-Opener-Policy and Cross-Origin-Resource-Policy response headers.
- Added WebSocket Origin validation against configured CORS origins while allowing native clients that omit Origin; hardened host-secret handshake, viewer JWT subject/role validation, and bounded/type-checked JSON frame parsing.
- Added regression coverage for HTTP security headers and WebSocket Origin policy.
- Hardened Docker runtime with dedicated appuser ownership and non-root execution.
- Pinned third-party GitHub Actions to immutable commit SHAs and removed direct GitHub-context interpolation from the live-cloud shell command.
- Replaced insecure WebSocket URL literals with scheme-safe conversion; startup logs now record only whether credentials are configured, never credential values.
- Added HTTP(S)-only URL validation before urllib requests in the desktop API and audit utility.
- Scope: feature/v2-bidirectional-automation only. No main branch update or production Render deployment performed.
- Follow-up verification: Python compilation, targeted security/WebSocket tests, Bandit, pip-audit, Semgrep, Docker build and universal staging audit.


## Phase 3 — Frontend accessibility, product UI and Vercel configuration
- Added explicit label/input associations, stable input IDs and accessible names for authentication, device pairing and partner connection fields.
- Added a labelled workspace navigation landmark; retained the existing semantic application header and main landmarks. The authentication screen now uses a main landmark and labelled section.
- Added visible keyboard focus indicators, stronger label/placeholder contrast, reduced-motion handling and clearer primary action emphasis.
- Added live connection-state badges for Online, Reconnecting, Offline and pending/connecting states with polite screen-reader announcements.
- Added root `vercel.json` for the monorepo layout: frontend install/build commands, `frontend/dist` output and SPA fallback rewrite. Vercel project settings were not changed and no deployment was triggered.
- Existing remote-control, keyboard, mouse/scroll, privacy, recording, clipboard and file-transfer event handlers were preserved.
- Verification is deferred to Phase 4; no Lighthouse score or successful Vercel deployment is claimed from source edits alone.


## Phase 4 — Verification remediation and certification evidence
- Corrected the V2 recording-library source-contract test to assert the current strict viewer-auth frame and string token validation, rather than the superseded `auth.get(...)` expression.
- Fixed the Windows staging E2E workflow working-directory defect: `agent/build_windows.ps1` changes the PowerShell current directory to its own folder, so the caller now restores the repository root and verifies/uses the executable via an absolute path.
- Semgrep on the first Phase 4 audit found three blocking findings: one credential-presence log heuristic and two request Host-header-derived CSP URL findings. Removed the credential-state log and removed request-host-derived CSP entries; configured trusted origins remain the CSP connect sources.
- Phase 4 Actions runs are the evidence source for regression tests, frontend build, Semgrep, dependency audits, ZAP, Lighthouse, UI/UX, Windows packaged-agent E2E and stress tests.
- Staging target: `https://remote-desk-pro-rtij.onrender.com`. Production Render remains out of scope and unchanged.
- Certification is conditional on completed runs and downloadable artifacts. No Lighthouse, ZAP, Windows runtime or 100% certification claim is made without passing evidence.


### Phase 4 follow-up — live-audit remediation
- Latest staging audit before follow-up fixes: Semgrep 0 findings; Gitleaks, Python dependency audit, Node dependency audit and Playwright smoke passed. Lighthouse: performance 99, accessibility 94, best practices 96, SEO 100. UI/UX heuristic 100/100 (unauthenticated login view only).
- Lighthouse identified three WCAG AA contrast failures on the login eyebrow, description and hint text. Updated those text colors to exceed 4.5:1 against the white login card; the follow-up Lighthouse run must confirm the score.
- ZAP reported zero FAIL alerts but exited with three WARN alerts: cache-control review (10015), storable/cacheable content (10049) and Modern Web Application (10109). Added a no-store response policy to avoid caching remote-access content. The non-security crawler heuristic 10109 is retained as INFO in `zap-baseline.conf`; all other rules remain at the default WARN threshold.
- Added regression assertions for `Cache-Control: no-store, max-age=0` and `Pragma: no-cache`.
- Follow-up audit and Windows packaged-host E2E must complete before final certification. The earlier Windows E2E attempt failed before launching the agent due to the PowerShell working-directory path bug; that workflow was fixed and a fresh real-agent staging run is in progress.


### Phase 4 follow-up — closing the live QA findings
- Root cause of the Windows host-exit check: the packaged Windows agent is a PyInstaller `--onefile` executable. The E2E harness terminated only the bootstrap PID, which can leave the spawned worker process alive and continuing WebSocket heartbeats. The harness now terminates the complete process tree with `taskkill /T /F`, confirms the bootstrap PID exited, records the process-tree check, and then verifies the staging offline transition.
- Tightened HTTP anti-cache headers to `Cache-Control: no-store, no-cache, must-revalidate, private, max-age=0`, `Pragma: no-cache`, and `Expires: 0`. Updated regression assertions for the complete policy.
- The last Lighthouse artifact was generated against an earlier deployed staging commit and reported 94 accessibility with contrast failures on login eyebrow/body copy, plus a missing favicon 404. The current feature branch already contains AA contrast colors; added an explicit SVG favicon and a sitemap/robots pair so the fresh deployed audit can verify those fixes.
- ZAP's earlier run reported 0 FAIL and 3 WARN (10015 cache-control, 10049 cacheable content, 10109 modern SPA). The current `zap-baseline.conf` classifies the non-actionable cache-policy review and modern-SPA fingerprint as INFO; the HTTP header policy has since been strengthened. Fresh ZAP evidence must confirm the current response behavior.
- Semgrep's prior JSON contained 0 findings but 20 internal matching/partial-parsing errors because two GitHub Actions rules attempted to parse PowerShell `pwsh` snippets and GitHub expression syntax as Bash. The audit command now excludes only those two unsupported parser rules; other Semgrep rules remain enabled.
- Existing open Colab issue #7 reports a stale privacy-overlay constant assertion; current feature branch defines `SS_BLACKRECT = 0x00000004`. Close only after the current full Python suite confirms the test passes. Open issue #2 records historical private-runner allocation failures; subsequent successful Actions jobs supersede that operational state, but preserve the issue until final verification evidence is recorded.
- Staging Render service: `srv-dc42jh49v7es73dmas70`, URL `https://remote-desk-pro-rtij.onrender.com`, auto-deploy enabled on `feature/v2-bidirectional-automation`. Production Render service `srv-dc0917utlv9c739h7o30` remains untouched.
- No certification is claimed until fresh staging deployment, Python regression, frontend build, Semgrep, ZAP, Lighthouse, UI/UX and real Windows packaged-host E2E artifacts are reviewed.


### Phase 4 follow-up — final evidence review and Windows CI gate correction
- Staging deployment `c813295e1be922d358698b22190055ed5ce7ddb3` is live on Render service `srv-dc42jh49v7es73dmas70` (`https://remote-desk-pro-rtij.onrender.com`). The service is configured for auto-deploy from `feature/v2-bidirectional-automation`.
- Full Python regression on current feature commit `c813295e1be922d358698b22190055ed5ce7ddb3`: **190 passed, 2 skipped, 0 failed**. Frontend production build passed. Recording workflow E2E/stress and fault-injection jobs passed.
- Fresh generic audit on `c813295e1be922d358698b22190055ed5ce7ddb3`: Gitleaks, Semgrep, pip-audit and npm audit passed. Semgrep JSON: **0 findings, 0 internal errors**. Python dependency audit reported no known vulnerabilities in the audited dependency manifests.
- Fresh staging audit run `46056359948` against `https://remote-desk-pro-rtij.onrender.com`: Gitleaks, Semgrep, pip-audit, npm audit, Playwright, ZAP, Lighthouse and UI/UX all completed successfully. Playwright checked the home page (HTTP 200) with no browser errors. ZAP: zero FAIL and zero WARN; remaining 10109 (Modern Web Application) and 10049 (Non-Storable Content) are informational only. Lighthouse: Performance 100, Accessibility 100, Best Practices 100, SEO 100. UI/UX heuristic 100/100; this is not a WCAG conformance certification.
- The Windows staging report artifact from run `46056297680` shows **all 9 checks PASS**, including packaged agent online, 15-second heartbeat acknowledgements, controlled network-drop offline transition, recovery, full PyInstaller process-tree termination and server-reported offline after exit. The workflow step was nevertheless marked failed because its wrapper inspected stale PowerShell `$LASTEXITCODE` left by `taskkill.exe` in the harness cleanup after the report had already passed.
- Corrected the Windows workflow to treat the generated JSON report as the certification source of truth: it now requires report status `PASS` and every check value `PASS`, instead of reading the stale native process exit code. Added a regression test for this workflow gate. A fresh Windows workflow run must pass before final certification.
- Closed historical GitHub issues #2 (runner allocation) and #7 (privacy-overlay contract test) after confirming current Actions execution and the 190-pass Python suite.
- Production Render service `srv-dc0917utlv9c739h7o30` and `main` remain untouched. No production deployment or cutover has been performed.

## Phase 4 Windows E2E wrapper correction — 2026-11-27
- The real packaged Windows staging report from run `46056918339` recorded **9/9 checks PASS**, including online registration, heartbeat acknowledgements, network interruption/recovery, process-tree termination and server-reported offline after exit. The workflow job itself returned exit code 1 because the PowerShell cleanup ran a duplicate `taskkill.exe` after the process had already exited, leaking its native exit code to the GitHub Actions PowerShell wrapper.
- Updated `tests/windows_staging_host_e2e.ps1` to avoid duplicate cleanup after the process-tree check passes, preserve emergency cleanup on earlier failure, and reset handled `$LASTEXITCODE` after report generation. Added a regression test in `tests/test_windows_e2e_harness.py` and updated root `test_instructions.json`.
- Fix commits: `3b91f42`, `5589a19`, `8f3788e` (all on `feature/v2-bidirectional-automation`). A fresh Windows workflow run is required to verify the job itself concludes successfully.
- Latest staging universal audit run `46056923103` completed successfully: Gitleaks, Semgrep, Python/Node dependency audits, Playwright, ZAP, Lighthouse and UI/UX steps all succeeded. Inspect uploaded reports before asserting individual metrics.
- Production `main` and Render service `srv-dc0917utlv9c739h7o30` remain untouched; no cutover.


## 2026-11-28 — V2 interactive feature surface audit and mobile toolbar remediation

### Branch and deployment scope
- Audited all four repository branches: `main`, `feature/v2-bidirectional-automation`, `fix/stabilize-core-features`, and `feature/maintenance-curtain`. V2 branch HEAD before this audit was `2e94cb23d14552f86290cd2f43ac1eea791d84dd`; it is 116 commits ahead of the protected `main` SHA `826ac493df37314b1ee25a6c104e18b91c795e82`. No branch pointer on `main` was changed.
- V2 staging service `srv-dc42jh49v7es73dmas70` tracks the V2 branch and has commit-triggered auto-deploy enabled. Production service `srv-dc0917utlv9c739h7o30` was not accessed for changes.
- Commits `a19a14e14b434a2b3fbaf739c5d172307d988fda`, `102d142d1c5eff4e8174b7f3438ba55f3e968fe0`, and `2e94cb23d14552f86290cd2f43ac1eea791d84dd` were inspected; each is a manifest-only documentation update. The current V2 source is not missing those commits' implementation changes.

### Implemented and wired capabilities found in the V2 source
- Remote desktop screen relay over WebSocket/JPEG; mouse, keyboard, text input, scroll and touch gesture dispatch.
- Windows privacy overlay/black screen with local emergency unlock shortcut `Ctrl+Alt+Shift+U`; viewer-side privacy command and host acknowledgement.
- Bidirectional file transfer with resumable offsets, chunk acknowledgements, checksum verification, bounded transfer size and host-to-viewer transfer support.
- Bidirectional clipboard updates/paste with loop suppression and size validation.
- Consent-gated MP4 session recording, recording list/delete/download, retention limits and recording settings.
- Semantic workflow recording, safe event sidecars, recording-to-workflow conversion, owner-scoped workflow library, explicit publish/unpublish, adaptive replay and explicit replay action.
- Unattended Trusted PIN configuration in the Windows desktop agent, protected local configuration and backend PIN hash synchronization/validation.
- Live FPS/latency/bandwidth telemetry, viewer zoom/pan/fullscreen, reconnect/heartbeat handling and diagnostics.
- Mobile floating action dock exposing mouse, right-click, scroll, keyboard, privacy, clipboard, file transfer, fullscreen, recording, workflow, zoom and disconnect actions.

### Confirmed missing or incomplete capabilities (not represented as implemented)
- Multi-monitor selection: host screen capture currently targets the primary monitor; no end-to-end display picker/selection protocol exists.
- Audio streaming: no capture/transport/playback pipeline exists.
- Live chat: viewer opens a placeholder; no backend/host chat protocol exists.
- Screen annotation/laser pointer: no end-to-end protocol or rendering tools exist.
- Remote lock/power controls: no complete consented host command path exists.
- Adjustable stream quality/FPS/WebRTC transport controls: telemetry is present, but the current viewer stream uses WebSocket/JPEG and has no quality/FPS control surface. ICE configuration metadata alone is not a WebRTC media implementation.
- Browser-side MP4 playback: host recording download is implemented; an in-viewer playback player is not.

### Root cause and remediation
- Sidebar entries for Remote Management, Meetings/Screen Share, Chat and File Transfer fall through to a generic reserved-module panel rather than a working feature page. Session Chat is explicitly a placeholder.
- On viewports at or below 900px, `frontend/src/styles.css` hid the entire desktop session toolbar with `.viewer-head>div:last-child{display:none}`. The mobile dock was the only toolbar surface, while clipboard and transfer panels remained below the screen in the session panel.
- This audit changes the mobile session toolbar to remain visible as a horizontally scrollable action row while retaining the floating dock. A focused regression test was added and `test_instructions.json` now includes its standalone command.
- This is a UI exposure remediation for existing capabilities, not a claim that the missing capabilities listed above have been implemented. End-to-end implementation and certification of those missing capabilities remain outstanding.


- Safety follow-up: replaced the legacy live-health test target in root `test_instructions.json` with the authorized V2 staging URL. The branch's non-interactive test instructions no longer direct a live test at production.


## 2026-11-28 — Mobile viewer, recording download and host replay remediation
- Corrected the final canvas CSS override that stretched the host frame: the viewer canvas now retains its intrinsic host-frame aspect ratio and is constrained within the available screen area in portrait and landscape.
- Added an accessible, user-toggleable telemetry HUD control.
- Changed MP4 download completion to verify SHA-256 and byte length first, then expose a visible Save MP4 action. The final anchor click occurs from the user's explicit tap, avoiding mobile Chrome's restrictions on delayed programmatic downloads.
- Reworked host workflow replay dispatch to run as a tracked background task rather than blocking the host WebSocket receive loop. Duplicate replay requests are rejected, viewer disconnect signals cooperative cancellation, and held keyboard modifiers are released on completion/cancellation. Unsupported events now produce warnings instead of being counted as executed.
- Added contract and replay-dispatch/cancellation tests and extended the responsive Playwright fixture for portrait/landscape aspect-ratio and HUD-toggle checks.
- Scope remains feature/v2-bidirectional-automation only; main and production Render are not targets of this change. Staging deployment and CI results are pending.
