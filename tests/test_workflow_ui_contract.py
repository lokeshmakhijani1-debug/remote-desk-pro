from pathlib import Path


def test_workflow_history_exposes_save_publish_unpublish_delete_and_recording_conversion():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    for marker in ("saveSelectedWorkflow", "publishSavedWorkflow", "unpublishSavedWorkflow",
                   "deleteSavedWorkflow", "recording_convert_workflow", "Convert to Workflow",
                   "workflow_export_start", "workflow_export_chunk", "workflow_export_end"):
        assert marker in source
