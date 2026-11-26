"""Additional deterministic coverage for the V2 production verification matrix.

Runtime-only desktop/browser scenarios remain covered by their dedicated platform
or cloud jobs; these tests assert the local contracts that can run in CI.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from agent import workflow_engine
from agent.workflow_engine import WorkflowRecorder
from backend import main as backend_main


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_t01_recording_timer_state_is_tied_to_recording_activity():
    app = _source("frontend/src/App.tsx")
    assert 'if(!recordingActive){setRecordingSeconds(0);return;}' in app
    assert "setInterval(()=>setRecordingSeconds(Math.floor((Date.now()-started)/1000)),1000)" in app
    assert "formatRecordingTime(recordingSeconds)" in app


def test_t09_recording_library_relay_is_approval_gated():
    source = inspect.getsource(backend_main.host_socket)
    for kind in ("recording_control", "recording_list_result", "recording_deleted", "recording_chunk_result"):
        assert kind in source
    assert "hub.is_approved(device_id)" in source
    assert "kind == \"recording_control\" and hub.is_approved(device_id)" in source


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
