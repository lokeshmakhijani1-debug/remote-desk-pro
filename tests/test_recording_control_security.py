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
