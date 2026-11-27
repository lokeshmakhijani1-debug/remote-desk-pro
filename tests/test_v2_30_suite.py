"""Additional deterministic coverage for the V2 production verification matrix.

Runtime-only desktop/browser scenarios remain covered by their dedicated platform
or cloud jobs; these tests assert the local contracts that can run in CI.
"""
from __future__ import annotations

import inspect
import asyncio
import json
import hashlib
import os
import sys
import threading
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent import workflow_engine
from agent.workflow_engine import WorkflowRecorder
from backend import main as backend_main
from backend.database import Base, User, Device, AuditEvent
from backend.security import hash_secret, issue_token
from agent import session_recorder as recorder_module
from agent.session_recorder import SessionRecorder, read_recording_chunk, cleanup_recordings
from agent import host_agent


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_t01_recording_timer_state_is_tied_to_recording_activity():
    app = _source("frontend/src/App.tsx")
    assert 'if(!recordingActive){setRecordingSeconds(0);return;}' in app
    assert "setInterval(()=>setRecordingSeconds(Math.floor((Date.now()-started)/1000)),1000)" in app
    assert "formatRecordingTime(recordingSeconds)" in app


def test_t09_recording_library_commands_require_authenticated_approved_viewer_and_host():
    viewer_source = inspect.getsource(backend_main.viewer_socket)
    host_source = inspect.getsource(backend_main.host_socket)
    for kind in ("recording_list", "recording_delete", "recording_download_chunk"):
        assert kind in viewer_source
    assert 'read_token(auth["session_token"]) if isinstance(auth.get("session_token"), str) else {}' in viewer_source
    assert 'if not isinstance(auth, dict) or auth.get("type") != "auth":' in viewer_source
    assert "kind in (\"recording_list\", \"recording_delete\", \"recording_download_chunk\") and user_role != \"read_only\"" in viewer_source
    assert "elif kind == \"recording_control\" and hub.is_approved(device_id)" in host_source
    assert "kind in (\"clipboard_ack\", \"privacy_screen_ack\", \"recording_status\", \"recording_list_result\", \"recording_deleted\", \"recording_chunk_result\", \"recording_error\") and hub.is_approved(device_id)" in host_source


def test_t10_storage_cap_removes_oldest_recordings_first(tmp_path):
    from agent.session_recorder import cleanup_recordings

    oldest = tmp_path / "session_oldest.mp4"
    newest = tmp_path / "session_newest.mp4"
    oldest.touch()
    newest.touch()
    oldest.write_bytes(b"")
    newest.write_bytes(b"")
    with oldest.open("wb") as stream:
        stream.truncate(60 * 1024 * 1024)
    with newest.open("wb") as stream:
        stream.truncate(60 * 1024 * 1024)
    import os
    os.utime(oldest, (100, 100))
    os.utime(newest, (200, 200))

    removed = cleanup_recordings(tmp_path, keep_last=10, max_storage_mb=100)

    assert removed == [oldest]
    assert not oldest.exists()
    assert newest.exists()


def test_t11_saved_recording_banner_has_keep_download_and_delete_actions():
    app = _source("frontend/src/App.tsx")
    assert 'className="recording-saved-banner"' in app
    assert "Keep / Download MP4" in app
    assert "Delete Recording" in app
    assert "downloadHostRecording(savedRecording.filename)" in app
    assert "deleteHostRecording(savedRecording.filename)" in app


def test_t12_recordings_manager_has_responsive_modal_contract():
    app = _source("frontend/src/App.tsx")
    css = _source("frontend/src/styles.css")
    assert 'className="recording-modal recordings-manager"' in app
    assert 'role="dialog"' in app
    assert ".recording-modal" in css
    assert "@media(max-width:680px)" in css
    assert "new ResizeObserver(refit)" in app
    assert 'addEventListener("orientationchange",refit' in app


def test_t13_workflow_recorder_captures_scroll_and_shortcut_actions(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow_engine, "_active_context", lambda: {})
    monkeypatch.setattr(workflow_engine, "_focused_input_state", lambda: {"focused": True, "editable": True})
    monkeypatch.setattr(workflow_engine, "_semantic_anchor_at", lambda *_: {})
    recorder = WorkflowRecorder(tmp_path)
    recorder.set_enabled(True)
    recorder.record_control({"event": "mouse_scroll", "deltaX": 120, "deltaY": -240, "x": 0.25, "y": 0.75})
    recorder.record_control({"event": "key_down", "key": "ctrl"})
    recorder.record_control({"event": "key_down", "key": "a"})
    path = recorder.set_enabled(False)

    import json
    steps = json.loads(path.read_text(encoding="utf-8"))["steps"]
    assert steps[0]["action"] == "mouse_scroll"
    assert (steps[0]["delta_x"], steps[0]["delta_y"]) == (120.0, -240.0)
    assert any(step["action"] == "clear_input" for step in steps)


def test_t19_workflow_replay_rejects_injected_command_fields():
    assert backend_main.validate_control({"type": "control", "event": "workflow_replay"})
    for payload in (
        {"type": "control", "event": "workflow_replay", "steps": [{"action": "delete"}]},
        {"type": "control", "event": "workflow_replay", "command": "shell"},
        {"type": "control", "event": "workflow_replay", "path": "../../secret"},
    ):
        assert not backend_main.validate_control(payload)


def test_t24_invalid_connection_attempts_are_rate_limited(monkeypatch):
    key = "v2-suite-invalid-pin"
    backend_main._attempts.pop(key, None)
    monkeypatch.setattr(backend_main.time, "monotonic", lambda: 1000.0)
    try:
        for _ in range(8):
            backend_main.enforce_rate_limit(key)
        with pytest.raises(HTTPException) as error:
            backend_main.enforce_rate_limit(key)
        assert error.value.status_code == 429
    finally:
        backend_main._attempts.pop(key, None)


def test_t25_privacy_overlay_registers_emergency_unlock_hotkey():
    overlay = _source("agent/privacy_overlay.py")
    assert 'user32.RegisterHotKey(None, 0x5244, 0x0002 | 0x0001 | 0x0004, ord("U"))' in overlay
    assert "msg.message == 0x0312 and msg.wParam == 0x5244" in overlay
    assert "self._stop_flag.set()" in overlay
    assert "user32.UnregisterHotKey(None, 0x5244)" in overlay


def test_t26_floating_dock_exposes_required_remote_actions():
    app = _source("frontend/src/App.tsx")
    for label in (
        "Mouse Mode", "Right-click", "Scroll Up", "Scroll Down",
        "Virtual Keyboard", "Privacy", "Start Recording", "Stop Recording",
        "File Transfer", "Clipboard Sync", "Zoom In", "Zoom Out",
        "Fullscreen", "Disconnect", "V2 AI Replay", "Workflow Steps",
        "Community Library",
    ):
        assert label in app
    assert 'className="mobile-action-dock"' in app


def test_t29_workflow_recorder_stress_is_bounded_and_repeatable(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow_engine, "_active_context", lambda: {})
    monkeypatch.setattr(workflow_engine, "_focused_input_state", lambda: {"focused": False, "editable": False})
    recorder = WorkflowRecorder(tmp_path)
    for _ in range(3):
        recorder.set_enabled(True)
        for _ in range(workflow_engine.MAX_STEPS + 100):
            recorder.record_control({"event": "mouse_scroll", "deltaX": 1, "deltaY": -1})
        recorder.set_enabled(False)
    assert recorder.last_saved is not None
    import json
    saved = json.loads(recorder.last_saved.read_text(encoding="utf-8"))
    assert saved["step_count"] <= workflow_engine.MAX_STEPS
    assert len(saved["steps"]) <= workflow_engine.MAX_STEPS

class _FastStopEvent:
    def __init__(self):
        self._event = threading.Event()
    def set(self):
        self._event.set()
    def is_set(self):
        return self._event.is_set()
    def wait(self, timeout=None):
        return self._event.wait(min(float(timeout or 0.001), 0.001))


class _FakeCapture:
    monitors = [None, {"width": 32, "height": 32}]
    def __init__(self, frame_seen):
        self.frame_seen = frame_seen
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def grab(self, _monitor):
        self.frame_seen.set()
        return types.SimpleNamespace(rgb=bytes(range(256)) * 12)



def _install_recorder_fakes(monkeypatch, tmp_path):
    import imageio_ffmpeg
    frame_seen = threading.Event()
    monkeypatch.setattr(recorder_module, "RECORDING_DIR", tmp_path)
    monkeypatch.setitem(sys.modules, "mss", types.SimpleNamespace(mss=lambda: _FakeCapture(frame_seen)))
    return frame_seen, imageio_ffmpeg

def test_t01_manual_recording_full_lifecycle_writes_mp4_hash_and_timer_contract(tmp_path, monkeypatch):
    frame_seen, ffmpeg = _install_recorder_fakes(monkeypatch, tmp_path)
    recorder = SessionRecorder("123456789", "viewer-1", fps=10)
    recorder._stop = _FastStopEvent()
    recorder.start()
    assert recorder.is_alive
    assert frame_seen.wait(2)
    recorder.stop()
    payload = recorder.path.read_bytes()
    assert len(payload) > 100 and payload[4:8] == b"ftyp"
    metadata_reader = ffmpeg.read_frames(str(recorder.path), pix_fmt="rgb24")
    metadata = next(metadata_reader)
    assert metadata["size"] == (32, 32)
    assert len(next(metadata_reader)) == 32 * 32 * 3
    metadata_reader.close()
    assert recorder.sha256 == hashlib.sha256(payload).hexdigest()
    audit = [json.loads(line) for line in recorder.audit_path.read_text().splitlines()]
    started = next(row for row in audit if row["event"] == "session_started")
    ended = next(row for row in audit if row["event"] == "session_ended")
    assert datetime.fromisoformat(ended["ended_at"]) >= datetime.fromisoformat(started["started_at"])
    app = _source("frontend/src/App.tsx")
    assert "setRecordingSeconds(Math.floor((Date.now()-started)/1000))" in app
    assert "if(!recordingActive){setRecordingSeconds(0);return;}" in app


def test_t04_manual_then_privacy_start_reuses_single_recorder(tmp_path, monkeypatch):
    frame_seen, ffmpeg = _install_recorder_fakes(monkeypatch, tmp_path)
    created = []
    def factory():
        item = SessionRecorder("123456789", "viewer-1", fps=10)
        item._stop = _FastStopEvent()
        created.append(item)
        return item
    manual, started = host_agent.start_recorder_once(None, factory)
    assert started is True
    assert frame_seen.wait(2)
    privacy, started_again = host_agent.start_recorder_once(manual, factory)
    assert privacy is manual and started_again is False
    assert len(created) == 1 and privacy._thread is manual._thread
    assert len(created) == 1
    privacy.stop()
    events = [json.loads(line)["event"] for line in privacy.audit_path.read_text().splitlines()]
    assert events.count("session_started") == 1 and events.count("session_ended") == 1


def test_t06_multi_chunk_download_reassembles_exact_sha256(tmp_path):
    original = bytes(range(256)) * 2048 + b"remote-desk-pro-final-chunk"
    path = tmp_path / "session_multichunk.mp4"
    path.write_bytes(original)
    expected = hashlib.sha256(original).hexdigest()
    assembled = bytearray()
    offset = 0
    while True:
        chunk = read_recording_chunk(path.name, offset=offset, length=131072, folder=tmp_path)
        data = __import__("base64").b64decode(chunk["data_b64"], validate=True)
        assembled.extend(data)
        offset += len(data)
        assert chunk["offset"] == offset - len(data)
        if chunk["eof"]:
            break
        assert data
    assert len(assembled) > 300_000 and bytes(assembled) == original
    assert hashlib.sha256(assembled).hexdigest() == expected


def test_t10_max_duration_auto_stops_and_retention_evicts_oldest(tmp_path, monkeypatch):
    frame_seen, ffmpeg = _install_recorder_fakes(monkeypatch, tmp_path)
    ticks = iter((100.0, 100.0, 102.0))
    monkeypatch.setattr(recorder_module, "time", types.SimpleNamespace(monotonic=lambda: next(ticks)))
    recorder = SessionRecorder("123456789", "viewer-1", max_duration_seconds=1)
    recorder._stop = _FastStopEvent()
    recorder.start()
    recorder._thread.join(timeout=3)
    assert not recorder.is_alive and recorder.sha256 is not None and frame_seen.is_set()
    events = [json.loads(line)["event"] for line in recorder.audit_path.read_text().splitlines()]
    assert "session_auto_stopped" in events and "session_ended" in events
    metadata_reader = ffmpeg.read_frames(str(recorder.path), pix_fmt="rgb24")
    assert next(metadata_reader)["size"] == (32, 32)
    assert len(next(metadata_reader)) == 32 * 32 * 3
    metadata_reader.close()
    oldest = tmp_path / "session_oldest.mp4"
    newest = tmp_path / "session_newest.mp4"
    oldest.write_bytes(b"x" * (60 * 1024 * 1024))
    newest.write_bytes(b"y" * (60 * 1024 * 1024))
    os.utime(oldest, (100, 100))
    os.utime(newest, (200, 200))
    assert cleanup_recordings(tmp_path, keep_last=10, max_storage_mb=100) == [oldest]
    assert not oldest.exists() and newest.exists()


def test_t16_resolution_mapping_is_stable_across_dpi_scales():
    from agent.adaptive_replay import resolve_target
    normalized = {"x": 0.5, "y": 0.25}
    for screen_size, expected in [
        ((1920, 1080), (960, 270)),
        ((2400, 1350), (1200, 337)),
        ((2880, 1620), (1440, 405)),
    ]:
        result = resolve_target(normalized, screen_size)
        assert (result["x"], result["y"]) == expected
        assert result["strategy"] == "normalized"
    mapped = resolve_target(normalized, (2880, 1620), (300, 120, 1500, 920))
    assert (mapped["x"], mapped["y"]) == (900, 320)
    assert mapped["strategy"] == "relative"


@pytest.fixture()
def v2_api_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        user = User(email="v2-suite@example.test", password_hash=hash_secret("test-password-not-used"), role="admin")
        db.add(user)
        db.commit()
        db.refresh(user)
        device_id = "987654321"
        device = Device(device_id=device_id, owner_id=user.id, name="V2 test host",
                        secret_hash=hash_secret("test-agent-secret"), password_hash=hash_secret("123456"),
                        password_expires_at=datetime.now(timezone.utc) + timedelta(days=1))
        db.add(device)
        db.add(AuditEvent(user_id=user.id, device_id=device_id, action="device.unattended_pin_hash",
                          detail=hash_secret("2580")))
        db.commit()
        token = issue_token(str(user.id), user.role)
    def override_db():
        with Session() as db:
            yield db
    backend_main.app.dependency_overrides[backend_main.db_session] = override_db
    try:
        with TestClient(backend_main.app) as client:
            yield client, token, device_id
    finally:
        backend_main.app.dependency_overrides.pop(backend_main.db_session, None)
        backend_main._attempts.pop("connect:testclient", None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_t21_public_workflow_publish_list_import_and_execute_replay(v2_api_client, tmp_path, monkeypatch):
    client, token, _device_id = v2_api_client
    headers = {"Authorization": "Bearer " + token}
    workflow = {
        "schema_version": 1, "coordinate_space": "normalized_0_to_1",
        "name": "Safe community replay", "tags": ["verification"],
        "notes": "Non-destructive mouse action fixture", "is_public": True,
        "privacy": {"typed_text_recorded": False, "clipboard_recorded": False, "local_only": False},
        "steps": [{"action": "mouse_down", "x": 0.5, "y": 0.25, "button": "left"}],
    }
    published = client.post("/api/workflows/publish", headers=headers, json={"workflow": workflow})
    assert published.status_code == 200
    workflow_id = published.json()["id"]
    listed = client.get("/api/workflows/community", headers=headers)
    assert listed.status_code == 200 and any(row["id"] == workflow_id for row in listed.json())
    imported = client.post(f"/api/workflows/import/{workflow_id}", headers=headers)
    assert imported.status_code == 200
    local = imported.json()["workflow"]
    assert local["is_public"] is False and local["privacy"]["local_only"] is True
    clicks = []
    fake_pyautogui = types.SimpleNamespace(
        FAILSAFE=True, KEYBOARD_KEYS=set(),
        size=lambda: (1920, 1080),
        click=lambda x, y, **kwargs: clicks.append((x, y, kwargs)),
    )
    monkeypatch.setitem(sys.modules, "pyautogui", fake_pyautogui)
    local_path = tmp_path / "community_import.json"
    local_path.write_text(json.dumps(local), encoding="utf-8")
    result = workflow_engine.WorkflowReplayEngine(tmp_path).replay(local_path)
    assert result["executed"] == 1 and result["warnings"] == []
    assert clicks == [(960, 270, {"button": "left"})]


def test_t23_valid_trusted_pin_connects_and_bypasses_manual_consent(v2_api_client, monkeypatch):
    client, token, device_id = v2_api_client
    monkeypatch.setenv("RDP_UNATTENDED_PIN", "2580")
    monkeypatch.setattr(host_agent, "_CONSENT_CALLBACK",
                        lambda *_: pytest.fail("manual consent must not be shown"))
    response = client.post("/api/devices/connect", headers={"Authorization": "Bearer " + token},
                           json={"device_id": device_id, "password": "2580"})
    assert response.status_code == 200 and response.json()["session_token"]
    assert asyncio.run(host_agent.approve_viewer_request(device_id, "unused")) is True


def test_t24_invalid_trusted_pin_is_rejected_and_connect_endpoint_rate_limits(v2_api_client):
    client, token, device_id = v2_api_client
    # TestClient reuses one synthetic source IP across the entire pytest process.
    # Isolate this test's rate-limit window without changing production throttling.
    backend_main._attempts.pop("connect:testclient", None)
    backend_main._attempts.pop(f"connect-device:testclient:{device_id}", None)
    headers = {"Authorization": "Bearer " + token}
    for _ in range(8):
        response = client.post("/api/devices/connect", headers=headers,
                               json={"device_id": device_id, "password": "9999"})
        assert response.status_code == 401
    limited = client.post("/api/devices/connect", headers=headers,
                          json={"device_id": device_id, "password": "9999"})
    assert limited.status_code == 429


def test_t29_two_hundred_host_input_events_and_rapid_recording_toggles(monkeypatch):
    calls = []
    fake_pyautogui = types.SimpleNamespace(
        FAILSAFE=False, KEYBOARD_KEYS={"ctrl", "a"},
        size=lambda: types.SimpleNamespace(width=1920, height=1080),
        moveTo=lambda x, y, **kwargs: calls.append(("move", x, y)),
        keyDown=lambda key, **kwargs: calls.append(("down", key)),
        keyUp=lambda key, **kwargs: calls.append(("up", key)),
        mouseDown=lambda button="left", **kwargs: calls.append(("mouse_down", button)),
        mouseUp=lambda button="left", **kwargs: calls.append(("mouse_up", button)),
    )
    monkeypatch.setitem(sys.modules, "pyautogui", fake_pyautogui)
    monkeypatch.setattr(host_agent, "_focus_target_at_cursor", lambda: None)
    monkeypatch.setattr(host_agent, "_PRIMARY_CAPTURE_SIZE", (1920, 1080, 1920, 1080))
    monkeypatch.setattr(host_agent, "_WORKFLOW_RECORDER", None)
    host_agent._PRESSED_KEYS.clear()
    host_agent._PRESSED_MOUSE_BUTTONS.clear()
    events = []
    for index in range(100):
        events.append({"event": "mouse_move", "x": (index % 10) / 10, "y": (index % 7) / 7})
        events.append({"event": "key_down" if index % 2 == 0 else "key_up", "key": "a"})
    for event in events:
        assert host_agent.apply_control(event) is True
    assert len(calls) == 200

    class ToggleRecorder:
        def __init__(self):
            self.is_alive = False
        def start(self):
            if self.is_alive:
                raise AssertionError("duplicate start")
            self.is_alive = True
        def stop(self):
            self.is_alive = False
    created = []
    active = None
    for _ in range(100):
        active, _ = host_agent.start_recorder_once(active, lambda: created.append(ToggleRecorder()) or created[-1])
        active.stop()
        active, _ = host_agent.start_recorder_once(active, lambda: created.append(ToggleRecorder()) or created[-1])
        active.stop()
    assert len(created) == 200 and active.is_alive is False
    assert not host_agent._PRESSED_KEYS and not host_agent._PRESSED_MOUSE_BUTTONS


def test_t30_manifest_exposes_render_git_sha_and_frontend_serving_is_build_aware(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "render-test-sha")
    result = backend_main.manifest()
    assert result["git_sha"] == "render-test-sha"
    assert result["deployment"]["git_sha"] == "render-test-sha"
    source = _source("backend/main.py")
    assert 'Path(__file__).resolve().parent.parent / "frontend" / "dist"' in source
    assert 'StaticFiles(directory=str(frontend_dist), html=True, check_dir=True)' in source
    html = _source("frontend/index.html")
    assert 'name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, viewport-fit=cover"' in html
