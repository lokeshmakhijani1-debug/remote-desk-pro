# Remote Desk Pro — Project State

**Updated:** 2026-11-27  
**Working branch:** `feature/v2-bidirectional-automation`  
**Repository:** `lokeshmakhijani1-debug/remote-desk-pro`

## Scope delivered on this branch
- Session recordings now have a companion event sidecar for replay-safe mouse clicks, scrolls, modifier/navigation keys, and clear-input actions.
- Printable keystrokes, typed text, clipboard contents, passwords, and arbitrary control payloads are excluded from the sidecar.
- Completed MP4 recordings with a matching sidecar convert into the existing schema-v1 workflow JSON format. Video-only MP4 files are rejected rather than guessed from pixels.
- Converted JSON is streamed through bounded, validated WebSocket frames and saved to an authenticated, owner-scoped backend workflow library.
- The API supports private save/list/delete and explicit publish/unpublish into the existing Community Library.
- Workflow History exposes conversion, save, list, delete, publish, unpublish, and an explicit **Replay Latest on Host** action.
- Replay continues through the existing host-side `WorkflowReplayEngine`; conversion and publication never execute a workflow automatically.
- Root `PROJECT_MANIFEST.md` and `test_instructions.json` were updated.

## Validation snapshot
| Area | Result | Evidence |
|---|---|---|
| Workflow conversion, sidecar privacy and malformed-timeline tests | PASS | Dedicated `workflow-pipeline` Actions job |
| Repeated replay-engine execution simulation | PASS | Same converted workflow replayed twice with mocked host input hooks |
| Saved workflow API owner isolation and lifecycle | PASS | Dedicated API tests |
| WebSocket conversion/export relay validation | PASS | Dedicated transport tests and stress harness |
| Frontend production build | PASS | Dedicated workflow-pipeline job |
| WebSocket concurrency/disconnect stress | PASS | `scripts/verify_websocket_stress.py --clients 12 --rounds 2`, including conversion/export frames |
| Fault-injection and load regression | PASS | `tests/test_load_and_fault_injection.py` and `tests/test_v2_fault_injection.py` |
| Gitleaks full-history scan | PASS | GitHub Actions |
| Windows agent packaging and checksum | PASS | Windows V2 executable job |
| Full legacy Python regression suite | FAIL — 3 existing privacy-overlay tests | `test_privacy_preview_and_native_overlay_are_pure_black`, `test_privacy_banner_is_disabled_off_windows`, `test_t25_privacy_overlay_registers_emergency_unlock_hotkey`; privacy-overlay implementation was not changed in this task |

## Not performed / remaining approvals
- No merge to `main`, production deployment, or release was performed.
- Supabase migration `20261127120000_saved_workflows.sql` is committed but has **not** been applied to the live database. Apply it through the approved database migration process before using the new persistence endpoints in production.
- The repository tree contained no MP4 or `.events.jsonl` recording assets. Host-local recordings could not be inspected through GitHub repository access. The converter/replay pipeline was validated with generated test fixtures, not a real user recording.
- Live Render E2E was not run because the existing headless script registers a persistent synthetic user/device in the live service; that production data mutation was not included in the granted scope.
- The Windows job built and checksummed the executable, but no physical Windows GUI/input replay was performed.
- The separate Windows laptop/local clone could not be inspected through the GitHub connector; no claim is made about its local repository state.
- No external API keys or new paid services were added. No new secrets are required; runtime configuration remains environment-gated.

## Safety and compatibility notes
- Host recording remains local-only. The server stores workflow JSON metadata, not the MP4 video.
- Public access requires an explicit publish action. Unpublish removes the public Community Library copy while retaining the private saved workflow.
- Workflow steps are restricted to replay-safe actions; printable keyboard keys and sensitive fields are rejected by the API.
- A replay is a real host input action. The user must explicitly choose **Replay Latest on Host** while connected to an approved host session.
- Existing privacy-overlay failures are recorded above and were intentionally left untouched to keep this feature change scoped.
