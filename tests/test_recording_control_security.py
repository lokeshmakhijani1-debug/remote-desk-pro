from backend.main import validate_recording_control


def test_recording_start_requires_bounded_local_settings():
    assert validate_recording_control({
        "type": "recording_control",
        "action": "start",
        "settings": {
            "max_duration_seconds": 1800,
            "retention_count": 5,
            "max_storage_mb": 1024,
            "save_mode": "local",
        },
    })


def test_recording_stop_needs_no_start_settings():
    assert validate_recording_control({"type": "recording_control", "action": "stop"})


def test_recording_publish_is_rejected_until_video_library_exists():
    assert not validate_recording_control({
        "action": "start",
        "settings": {"max_duration_seconds": 1800, "retention_count": 5,
                     "max_storage_mb": 1024, "save_mode": "community"},
    })


def test_recording_limits_reject_invalid_or_unbounded_values():
    base = {"max_duration_seconds": 1800, "retention_count": 5, "max_storage_mb": 1024, "save_mode": "local"}
    for field, value in (
        ("max_duration_seconds", 1),
        ("max_duration_seconds", 14401),
        ("retention_count", 0),
        ("retention_count", 101),
        ("max_storage_mb", 99),
        ("max_storage_mb", 20481),
        ("max_storage_mb", True),
    ):
        settings = {**base, field: value}
        assert not validate_recording_control({"action": "start", "settings": settings})


def test_unknown_recording_action_is_rejected():
    assert not validate_recording_control({"action": "upload"})


import base64
import hashlib
import json
import os
import pytest
from agent.session_recorder import list_recordings, delete_recording, read_recording_chunk
from backend.main import validate_recording_library_control


def test_list_recordings_returns_hashes_and_newest_first(tmp_path):
    older = tmp_path / "session_old.mp4"
    newer = tmp_path / "session_new.mp4"
    older.write_bytes(b"older")
    newer.write_bytes(b"newer-data")
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))
    rows = list_recordings(tmp_path)
    assert [row["filename"] for row in rows] == ["session_new.mp4", "session_old.mp4"]
    assert rows[0]["sha256"] == hashlib.sha256(b"newer-data").hexdigest()
    assert rows[0]["size_bytes"] == 10


def test_list_recordings_skips_symlinks_and_non_mp4(tmp_path):
    (tmp_path / "session_real.mp4").write_bytes(b"ok")
    (tmp_path / "session_note.txt").write_text("not video")
    try:
        (tmp_path / "session_link.mp4").symlink_to(tmp_path / "session_real.mp4")
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable")
    assert [row["filename"] for row in list_recordings(tmp_path)] == ["session_real.mp4"]


def test_delete_recording_audits_and_removes_file(tmp_path):
    target = tmp_path / "session_delete.mp4"
    target.write_bytes(b"recording")
    assert delete_recording(target.name, tmp_path) is True
    assert not target.exists()
    audit = (tmp_path / "audit.jsonl").read_text()
    assert '"event": "recording_deleted"' in audit
    assert '"recording": "session_delete.mp4"' in audit


@pytest.mark.parametrize("filename", ["../secret.mp4", "session_../../secret.mp4", "other.mp4", "", "session_bad/name.mp4"])
def test_delete_and_read_reject_invalid_filenames(tmp_path, filename):
    with pytest.raises(ValueError):
        delete_recording(filename, tmp_path)
    with pytest.raises(ValueError):
        read_recording_chunk(filename, folder=tmp_path)


def test_delete_and_read_reject_symlink(tmp_path):
    outside = tmp_path.parent / "outside.mp4"
    outside.write_bytes(b"secret")
    link = tmp_path / "session_link.mp4"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(ValueError):
        delete_recording(link.name, tmp_path)
    with pytest.raises(ValueError):
        read_recording_chunk(link.name, folder=tmp_path)
    assert outside.read_bytes() == b"secret"


def test_read_recording_chunk_is_bounded_and_reports_eof(tmp_path):
    payload = bytes(range(256)) * 700
    (tmp_path / "session_chunks.mp4").write_bytes(payload)
    result = read_recording_chunk("session_chunks.mp4", 100, 2048, tmp_path)
    assert base64.b64decode(result["data_b64"]) == payload[100:2148]
    assert result["offset"] == 100 and result["total_bytes"] == len(payload)
    assert result["eof"] is False
    assert result["sha256"] == hashlib.sha256(payload).hexdigest()
    with pytest.raises(ValueError):
        read_recording_chunk("session_chunks.mp4", 0, 262145, tmp_path)
    with pytest.raises(ValueError):
        read_recording_chunk("session_chunks.mp4", -1, folder=tmp_path)


def test_recording_library_control_schema_accepts_only_bounded_actions():
    assert validate_recording_library_control({"type": "recording_list"})
    assert validate_recording_library_control({"type": "recording_delete", "filename": "session_a-1.mp4"})
    assert validate_recording_library_control({"type": "recording_download_chunk", "filename": "session_a.mp4", "offset": 0})
    assert not validate_recording_library_control({"type": "recording_delete", "filename": "../secret.mp4"})
    assert not validate_recording_library_control({"type": "recording_download_chunk", "filename": "session_a.mp4", "offset": -1})
    assert not validate_recording_library_control({"type": "recording_download_chunk", "filename": "session_a.mp4", "offset": True})
    assert not validate_recording_library_control({"type": "recording_download_chunk", "filename": "session_a.mp4", "length": 262145})
    assert not validate_recording_library_control({"type": "recording_list", "filename": "unexpected"})
