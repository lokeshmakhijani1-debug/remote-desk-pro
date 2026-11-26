from pathlib import Path

from agent.session_recorder import SessionRecorder, cleanup_recordings


def test_session_recording_is_not_started_by_construction(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.session_recorder.RECORDING_DIR", tmp_path)
    recorder = SessionRecorder("123456789", "viewer-1")
    assert recorder.is_alive is False
    assert recorder.sha256 is None
    assert recorder.max_duration_seconds == 1800
    assert recorder.retention_count == 5
    assert recorder.max_storage_mb == 1024


def test_recording_settings_are_bounded():
    recorder = SessionRecorder(
        "123456789",
        "viewer-1",
        max_duration_seconds=999999,
        retention_count=999,
        max_storage_mb=999999,
    )
    assert recorder.max_duration_seconds == 14400
    assert recorder.retention_count == 100
    assert recorder.max_storage_mb == 20480


def test_cleanup_keeps_newest_recordings_within_count(tmp_path):
    recordings = []
    for index in range(4):
        path = tmp_path / f"session_device_{index}.mp4"
        path.write_bytes(bytes([index]) * 16)
        recordings.append(path)
    for index, path in enumerate(recordings):
        path.touch()
        import os
        os.utime(path, (1000 + index, 1000 + index))

    removed = cleanup_recordings(tmp_path, keep_last=2, max_storage_mb=100)
    assert len(removed) == 2
    assert recordings[0].exists() is False
    assert recordings[1].exists() is False
    assert recordings[2].exists()
    assert recordings[3].exists()


def test_cleanup_does_not_follow_paths_outside_recording_folder(tmp_path):
    root = tmp_path / "recordings"
    root.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"keep")
    try:
        (root / "session_link.mp4").symlink_to(outside)
    except OSError:
        import pytest
        pytest.skip("Symlink privilege unavailable on Windows")
    cleanup_recordings(root, keep_last=1, max_storage_mb=100)
    assert outside.read_bytes() == b"keep"
