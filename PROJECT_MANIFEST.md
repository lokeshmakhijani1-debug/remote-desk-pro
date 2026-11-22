# Remote Desk Pro â€” Project Manifest

**Workspace:** E:\GitHub-Vault\remote-desk-pro  
**GitHub:** https://github.com/lokeshmakhijani1-debug/remote-desk-pro (private)  
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
- Clipboard sync is bidirectional after host approval (64 KiB cap). File transfer is viewer-to-host only (50 MiB cap) with host-selected save path; chat delivery, audio, recording, multi-monitor switching, WOL, unattended access and user-invitation administration are not implemented.
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
- Public application: https://remote-desk-pro-pj29.onrender.com â€” fetched successfully; title `Remote Desk Pro`; sign-in/create-account landing screen rendered.
- Health endpoint: https://remote-desk-pro-pj29.onrender.com/api/health â€” fetched successfully; body reports `status: ok`, service `remote-desk-pro`, version `0.1.0`, database `configured`, capacity target `50`.
- Manifest endpoint: https://remote-desk-pro-pj29.onrender.com/api/manifest â€” fetched successfully; reports WebSocket binary relay and device pairing enabled; file transfer, clipboard sync and recording disabled.
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
- Desktop Commander device `DESKTOP-OLL6O6U` (ID `c895725a-c3f5-496f-9d75-9b751772e22c`) is currently offline (last seen 30 minutes ago). Step 6.3/6.4 cannot be executed until the laptop agent reconnects.
- Live WebSocket, clipboard, file-transfer, audit, PyInstaller, and local-to-cloud smoke tests remain **not run**. Do not treat feature flags or deployment status as E2E verification.


## Phase 6 final verification â€” 2026-11-21 (IST)
This final checkpoint supersedes the earlier Phase 6 pending/blocked notes above.

### 6.1 â€” PostgreSQL health and URL normalization
- Commit: `d6a4c3b55ccf09f657ec2b5e88165621bb717e09`; Render deployment: `dep-dc09rdivcj2c73dka2s0` (**live**).
- `backend/database.py` now calls `url.strip()` before SQLAlchemy parses or normalizes the environment URL, removing trailing CR, LF, tabs, spaces, and other surrounding whitespace.
- Verified from the connected Windows laptop against `https://remote-desk-pro-pj29.onrender.com/api/health`: HTTP 200, `status=ok`, `database=postgresql`.
- No database password or connection URI is stored in this repository or this manifest.

### 6.2 â€” Live WebSocket relay, clipboard, file transfer, and audit verification
- Added `tests/e2e_live_relay.py`; added `websockets>=13,<16` to `requirements-dev.txt`.
- First live E2E run: synthetic admin account `rdp-e2e-3948c60c942d@example.com`, device `636616212`. Passed PostgreSQL health, account/device registration, host online presence, 35-byte binary frame relay, bidirectional clipboard, file offer/accept/chunk/complete (4,440 bytes), path basename sanitization, and persistent audit retrieval.
- Audit API confirmed `rdp_audit_events` contained `device.paired`, `session.requested`, `session.host_approved`, `clipboard.relayed`, `file.offered`, and `file.received` for the synthetic device.
- Second live E2E run: synthetic technician account `rdp-e2e-b9e442dbeacb@example.com`, device `104028049`. Passed PostgreSQL health, registration, online presence, 35-byte binary frame relay, bidirectional clipboard, safe filename handling, and multi-chunk file transfer of 185,000 bytes across 4 chunks. Audit retrieval was not repeated in this second run because the synthetic user was a technician; audit persistence had already passed in the first admin run.
- These are synthetic protocol tests, not a full visual desktop-interaction or 50-user load test.
- Synthetic test accounts/devices remain in the application database as test artifacts: admin E2E account `rdp-e2e-3948c60c942d@example.com` / device `636616212`; multi-chunk E2E technician `rdp-e2e-b9e442dbeacb@example.com` / device `104028049`; pre-final-deploy host pairing `rdp-host-smoke-779dc761d2fd@example.com` / device `521743345`; final live host pairing `rdp-host-final-1ca979e7ae60@example.com` / device `827335259`. The first account received the initial admin role because it was the first account in the dedicated app tables; its generated password was not retained. No account/device deletion was attempted because the app currently has no safe self-service cleanup endpoint and destructive DB cleanup was not authorized.

### 6.3 â€” Standalone Windows agent build
- Build completed on `DESKTOP-OLL6O6U` using Python 3.14.0 and PyInstaller 6.22.3.
- Verified executable: `E:\\GitHub-Vault\\remote-desk-pro-main\\agent\\dist\\RemoteDeskPro-Agent.exe`.
- Size: 21,302,595 bytes; SHA-256: `27AC654E1750BE03603F40D93ECEE094A53D523039837E1CD0E6A38559856AF9`.
- Standalone `--help` startup/import check passed. EXE/build intermediates and local pairing credentials are excluded from Git; no secrets are committed.

### 6.4 â€” Local-to-cloud pairing smoke test
- Launched the built EXE on `DESKTOP-OLL6O6U`; Render authenticated `GET /api/devices` confirmed the host online.
- Final post-deploy smoke-test device: `827335259`; account: `rdp-host-final-1ca979e7ae60@example.com`; host process PID at launch: `10692`.
- After the final Render auto-deploy completed, the EXE was relaunched and authenticated `GET /api/devices` again confirmed the host online. Host process remains running and connected. Visible per-session consent remains enabled; unattended access is disabled; no viewer session was started during this pairing check.
- The EXE remains local at the path above and is not uploaded to GitHub.

### Verification boundaries
- Confirmed: PostgreSQL connection; URL whitespace normalization; host/viewer WebSocket authentication; online state; binary frame relay; bidirectional clipboard; multi-chunk viewer-to-host file relay; safe basename handling; audit persistence; Windows EXE build; local-to-cloud host pairing.
- Not certified: WebRTC peer-to-peer media (not implemented), file checksum/resume/AV scanning, host-to-viewer file transfer, unattended access, full remote-control UX, audio/recording, penetration testing, and concurrent-load capacity.

## Windows build refresh â€” 2026-11-21 (IST)
- Source branch: `main`; fetched and fast-forward pulled from `origin/main` (already up to date).
- Source commit: `24a56af636c0a27040b8a2e03f58ca3efd2baa4c`.
- Build host: `DESKTOP-OLL6O6U` (Windows 10 build 19045); Python `3.14.0`; PyInstaller `6.22.3`.
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
- Live Render E2E: PASS against `https://remote-desk-pro-pj29.onrender.com` after deployment of `2a08441`. Verified same-account registration/pairing, password rotation invalidation with existing viewer-token continuity, host approval, bidirectional clipboard relay, 185,000-byte chunked file transfer, explicit one-viewer rejection (`viewer_rejected`), heartbeat acknowledgement, and host reconnect while the viewer remained connected. The test creates synthetic @example.com accounts/devices; these test records were not deleted.
- Audit persistence: PASS — a read-only Supabase query on project `qxssuczpumsaqywifirv` confirmed 12 `rdp_audit_events` rows for the successful synthetic E2E device, including device pairing/password rotation, session request/approval, clipboard relay, file offer/receipt, and host disconnect. The test account is a technician, so the admin-only audit API was not used; direct read-only database verification confirmed persistence.
- Render service: remote-desk-pro-pj29 (srv-dc0917utlv9c739h7o30), branch main, auto-deploy enabled, verified URL https://remote-desk-pro-pj29.onrender.com; /api/health returns HTTP 200, status=ok, database=postgresql.
- Requested alias https://desk-pro-pi29.onrender.com returns HTTP 404 and is not configured as the agent default.
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
- Public URL after the Render deployment containing this commit is live: https://remote-desk-pro-pj29.onrender.com/download/agent
- The GitHub repository remains private; the Render download endpoint is the public distribution path and does not require GitHub repository access.

### Authoritative standalone build
- Build host: DESKTOP-OLL6O6U, Windows 10 build 19045.
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
- Public download URL: https://remote-desk-pro-pj29.onrender.com/download/agent


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
$ErrorActionPreference='Stop'; $base='https://remote-desk-pro-pj29.onrender.com'; $exe=Join-Path $env:LOCALAPPDATA 'RemoteDeskPro\RemoteDeskPro-Agent.exe'; New-Item -ItemType Directory -Force (Split-Path $exe) | Out-Null; Invoke-WebRequest "$base/download/agent" -OutFile $exe; $expected='REPLACE_WITH_NEW_ACTIONS_SHA256'; $actual=(Get-FileHash $exe -Algorithm SHA256).Hash; if($actual -ne $expected){throw "Build checksum mismatch; wait for new Actions artifact."}; Start-Process $exe; Start-Sleep -Seconds 15; python tests/e2e_remote_control_live.py
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
- No .env files or secret values were changed. Deployment target remains Render https://remote-desk-pro-pj29.onrender.com; Vercel is not used.

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


## Remote Desk Pro viewer, transfer and privacy fixes (2026-11-22)
- Viewer gestures: one-finger viewport pan works at 1x and above when Control is off; two-finger pinch/pan is available regardless of Control mode; zoom is clamped to 1x–4x. Control-mode one-finger pointer events retain remote mouse dispatch. Keyboard input element handlers are unchanged.
- Clipboard: retained viewer clipboard_paste request and host clipboard copy/Ctrl+V/clipboard_ack flow; added direct clipboard delivery regression coverage.
- File transfer: approved remote sessions automatically receive files into %USERPROFILE%\Downloads\RemoteDeskPro-Received\; resumable receiver offsets acknowledge each chunk and final SHA-256 verification is reported to the viewer.
- Privacy Screen: viewer offers Black Curtain and Technician Working Banner. Windows overlay uses topmost/tool-window extended styles, requests WDA_EXCLUDEFROMCAPTURE, blocks local interaction with a Tk grab, supports Ctrl+Alt+Shift+U emergency unlock, and is torn down on viewer disconnect.
- Protected behavior: existing mobile keyboard sendText/sendTextKey path, live JPEG stream, mouse dispatch, and SessionRecorder start/stop logic were not rewritten.
- Verification: CI and Render headless cloud E2E passed on 2026-11-22; physical Windows desktop input/overlay certification remains separate.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: a5eeefa9102cd4893fbc282a8b72080001f32f2c.
- EXE size: 61077813 bytes.
- EXE SHA-256: 05EBD0781250682FAADEE962CC65334EF3EDD3578B6C06E950111ED3514303E8.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 1ba57fd5f3ad6a4dd9a796c67a0e2e793af78178.
- EXE size: 61077936 bytes.
- EXE SHA-256: 3CEE09EB405318D6322D6D6E3530442DCB59D235707C9D4F8594F16E7AA86EAC.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.


## Final certification snapshot (2026-11-22)
- Current source branch: main; Windows build workflow source includes the full viewer, host-agent and privacy-overlay implementation. The build workflow published its generated EXE and committed the distribution copy plus manifest update.
- Backend/frontend CI: PASS — run 45027987877 (frontend build and backend pytest suite).
- Render headless protocol E2E: PASS — run 45027845280. Clipboard paste ACK, mobile text relay, live WebSocket frame delivery, both privacy-screen modes, MP4 recording cleanup, fresh-consent reconnect, PostgreSQL health and 2 MiB interrupted/resumed Zstandard transfer with SHA-256 all passed.
- Windows Agent build: PASS — run 45027914341; EXE 61,077,936 bytes; SHA-256 3CEE09EB405318D6322D6D6E3530442DCB59D235707C9D4F8594F16E7AA86EAC.
- Release asset: latest-agent / RemoteDeskPro-Agent.exe. Render-served binary path: backend/downloads/RemoteDeskPro-Agent.exe.
- Render deployment: service remote-desk-pro-pj29, deploy dep-dc1etsrbc2fs73e8l94g, commit a13e2577d77b987da0f6f7d397b56be0505ab456, status LIVE.
- The Live Cloud E2E workflow now also runs tests/e2e_live_relay.py against Render before the headless browser protocol test. Its first result is pending after the workflow update.
- tests/e2e_remote_control_live.py compiles in CI and now contains a two-finger pinch/no-accidental-click check. Its full run still requires the registered interactive Windows host with its DPAPI-protected agent config; no local machine was accessed for this task.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 5ee7497369aa0c438304842df39fe3178d58c450.
- EXE size: 61078350 bytes.
- EXE SHA-256: B1290690EC9BE8FCD57F986C0CAC9E3E621A6CF879F28AFF0ABB9EA6646C1948.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 831a3295db6e40ac540798990049d12e1c74b616.
- EXE size: 61079077 bytes.
- EXE SHA-256: 38C63E9B0BAFF05F5E5A6A75ECA7FBA268976D4D52B810BEEF9D2414E4D3ABA3.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.

## GitHub Actions Windows build (latest)
- Workflow: .github/workflows/build-windows.yml (windows-latest, Python 3.12, PyInstaller onefile/windowed).
- Build source: 78a0bc439ab74fa6d436baa7a5c325e8b35fbcb6.
- EXE size: 61078410 bytes.
- EXE SHA-256: BFC166B677E640E2D7B0F444A6EF1BD8E95B3B44667790F9220DF1B8A78F58B9.
- Distribution: backend/downloads/RemoteDeskPro-Agent.exe, served by Render /download/agent and /api/download/agent.
- Release: latest-agent (private repository release asset; Render distribution uses the committed binary).
- Local Windows remote-input and file-transfer E2E remains pending; cloud build success is not a live desktop certification.
