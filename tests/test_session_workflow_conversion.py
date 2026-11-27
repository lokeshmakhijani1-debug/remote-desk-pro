import json
import time
from types import SimpleNamespace

import pytest

import agent.session_recorder as session_recorder
import agent.workflow_engine as workflow_engine
from agent.session_recorder import SessionRecorder
from agent.workflow_engine import WorkflowReplayEngine, convert_session_recording_to_workflow


def test_session_recorder_sidecar_omits_printable_text_and_clipboard(tmp_path, monkeypatch):
    monkeypatch.setattr(session_recorder, "RECORDING_DIR", tmp_path / "recordings")
    monkeypatch.setattr(SessionRecorder, "is_alive", property(lambda self: True))
    recorder = SessionRecorder("123456789", "viewer", fps=1)
    recorder.started_monotonic = time.monotonic()
    assert recorder.record_control_event({"event": "mouse_down", "x": 0.25, "y": 0.75, "button": 0})
    assert not recorder.record_control_event({"event": "text_input", "text": "private-value"})
    assert not recorder.record_control_event({"event": "clipboard_paste", "text": "private-value"})
    assert recorder.record_control_event({"event": "key_down", "key": "ctrl"})
    assert recorder.record_control_event({"event": "key_down", "key": "a"})
    events = [json.loads(line) for line in recorder.events_path.read_text(encoding="utf-8").splitlines()]
    assert [item["event"] for item in events] == ["mouse_down", "key_down", "clear_input"]
    assert "private-value" not in recorder.events_path.read_text(encoding="utf-8")


def test_recording_converter_repeat_replays_with_existing_engine(tmp_path, monkeypatch):
    recording_dir, workflow_dir = tmp_path / "recordings", tmp_path / "workflows"
    recording_dir.mkdir()
    video = recording_dir / "session_device_20261127.mp4"
    video.write_bytes(b"test-mp4-placeholder-bytes")
    video.with_suffix(".events.jsonl").write_text("\n".join([
        json.dumps({"event": "mouse_down", "elapsed_ms": 100, "x": 0.2, "y": 0.8, "button": "left"}),
        json.dumps({"event": "key_down", "elapsed_ms": 220, "key": "ctrl"}),
        json.dumps({"event": "clear_input", "elapsed_ms": 250}),
        json.dumps({"event": "key_up", "elapsed_ms": 300, "key": "ctrl"}),
    ]) + "\n", encoding="utf-8")
    converted = convert_session_recording_to_workflow(video.name, recording_dir, workflow_dir)
    payload = json.loads(converted.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["source_recording"]["filename"] == video.name
    assert payload["privacy"]["typed_text_recorded"] is False
    assert payload["privacy"]["clipboard_recorded"] is False
    assert [step["action"] for step in payload["steps"]] == ["mouse_down", "key_down", "clear_input", "key_up"]
    assert payload["steps"][0]["delay_ms"] == 100 and payload["steps"][0]["x"] == 0.2
    assert payload["steps"][2]["action"] == "clear_input"
    assert payload["steps"][2]["x"] == 0.2 and payload["steps"][2]["y"] == 0.8

    calls = {"click": 0, "key_down": 0, "key_up": 0, "hotkey": 0}
    fake = SimpleNamespace(FAILSAFE=True, KEYBOARD_KEYS={"ctrl", "enter", "tab"},
                           size=lambda: (1000, 800),
                           click=lambda *a, **k: calls.__setitem__("click", calls["click"] + 1),
                           keyDown=lambda *a, **k: calls.__setitem__("key_down", calls["key_down"] + 1),
                           keyUp=lambda *a, **k: calls.__setitem__("key_up", calls["key_up"] + 1),
                           hotkey=lambda *a, **k: calls.__setitem__("hotkey", calls["hotkey"] + 1))
    monkeypatch.setitem(__import__("sys").modules, "pyautogui", fake)
    monkeypatch.setattr(workflow_engine, "resolve_target", lambda step, size, bounds, **kw: {"x": 200, "y": 300, "strategy": "test", "attempts": 1})
    monkeypatch.setattr(workflow_engine, "clear_input_and_verify", lambda control, key_sender, *a, **k: (key_sender() or True))
    monkeypatch.setattr(workflow_engine, "dismiss_known_popups", lambda *a, **k: False)
    monkeypatch.setattr(workflow_engine.time, "sleep", lambda *_: None)
    engine = WorkflowReplayEngine(workflow_dir)
    first, second = engine.replay(converted), engine.replay(converted)
    assert first["executed"] == second["executed"] == 4
    assert calls == {"click": 4, "key_down": 2, "key_up": 2, "hotkey": 2}


def test_video_only_recording_is_not_falsely_converted(tmp_path):
    video = tmp_path / "session_video_only.mp4"
    video.write_bytes(b"video-without-control-events")
    with pytest.raises(ValueError, match="sidecar"):
        convert_session_recording_to_workflow(video.name, tmp_path, tmp_path / "workflows")


def test_converter_rejects_clear_input_without_focus_target(tmp_path):
    video = tmp_path / "session_no_pointer.mp4"
    video.write_bytes(b"mp4")
    video.with_suffix(".events.jsonl").write_text(
        json.dumps({"event": "clear_input", "elapsed_ms": 100}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="focus coordinates"):
        convert_session_recording_to_workflow(video.name, tmp_path, tmp_path / "workflows")


def test_converter_rejects_out_of_order_event_timeline(tmp_path):
    video = tmp_path / "session_bad_timeline.mp4"
    video.write_bytes(b"mp4")
    video.with_suffix(".events.jsonl").write_text(
        json.dumps({"event": "mouse_down", "elapsed_ms": 200, "x": 0.2, "y": 0.2}) + "\n" +
        json.dumps({"event": "mouse_down", "elapsed_ms": 100, "x": 0.3, "y": 0.3}) + "\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="timeline"):
        convert_session_recording_to_workflow(video.name, tmp_path, tmp_path / "workflows")
