from backend.main import validate_recording_library_control, validate_workflow_export


def test_recording_conversion_requires_exact_validated_filename():
    assert validate_recording_library_control({"type": "recording_convert_workflow", "filename": "session_a.mp4"})
    assert not validate_recording_library_control({"type": "recording_convert_workflow", "filename": "../session_a.mp4"})
    assert not validate_recording_library_control({"type": "recording_convert_workflow", "filename": "session_a.mp4", "path": "/tmp"})


def test_workflow_export_frames_are_bounded_and_correlated():
    export_id = "a" * 24
    assert validate_workflow_export({"type": "workflow_export_start", "export_id": export_id,
                                     "filename": "workflow_20261127T120000000000Z.json", "total_bytes": 2048})
    assert validate_workflow_export({"type": "workflow_export_chunk", "export_id": export_id, "data": "x" * 10000})
    assert validate_workflow_export({"type": "workflow_export_end", "export_id": export_id})
    assert not validate_workflow_export({"type": "workflow_export_chunk", "export_id": export_id, "data": "x" * 40001})
    assert not validate_workflow_export({"type": "workflow_export_start", "export_id": "invalid",
                                         "filename": "../evil.json", "total_bytes": 100})
