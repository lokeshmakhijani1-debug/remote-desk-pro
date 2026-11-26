"""Contract tests for privacy-triggered host recording and viewer disclosure."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT / "agent" / "host_agent.py").read_text(encoding="utf-8")
VIEWER = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")


def test_privacy_enable_starts_a_distinct_security_recording():
    assert 'await apply_recording_action("privacy_start")' in HOST
    assert 'recording_reason = "privacy" if action == "privacy_start" else "manual"' in HOST
    assert '"Auto-recording active while screen is blanked"' in HOST


def test_privacy_disable_stops_only_privacy_triggered_recording():
    assert 'await apply_recording_action("privacy_stop")' in HOST
    assert 'recording_reason == "privacy"' in HOST
    assert "Manual recording continues after the privacy screen is removed." in HOST


def test_privacy_recording_cannot_be_manually_stopped_while_blanked():
    assert 'action == "stop" and _PRIVACY_SCREEN_ACTIVE' in HOST
    assert "Privacy-triggered recording cannot be stopped while the host screen remains blanked." in HOST


def test_viewer_discloses_privacy_auto_recording_state():
    assert 'recordingReason==="privacy"&&privacyEnabled' in VIEWER
    assert "Auto-recording active while screen is blanked" in VIEWER
