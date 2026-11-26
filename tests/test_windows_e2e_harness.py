import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_windows_e2e import launch_verified_agent, verify_agent


def write_fixture(tmp_path: Path, payload: bytes) -> tuple[Path, Path]:
    executable = tmp_path / "RemoteDeskPro-Agent.exe"
    executable.write_bytes(payload)
    metadata = tmp_path / "agent-build.json"
    metadata.write_text(json.dumps({
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }), encoding="utf-8")
    return executable, metadata


def test_agent_harness_accepts_matching_size_and_sha256(tmp_path):
    executable, metadata = write_fixture(tmp_path, b"safe-agent-fixture")
    result = verify_agent(executable, metadata)
    assert result["size_bytes"] == len(b"safe-agent-fixture")
    assert result["sha256"] == hashlib.sha256(b"safe-agent-fixture").hexdigest()


def test_agent_harness_rejects_modified_binary_before_launch(tmp_path):
    executable, metadata = write_fixture(tmp_path, b"original-agent")
    executable.write_bytes(b"tampered-agent")
    launches = []

    with pytest.raises(ValueError, match="size mismatch|SHA-256 mismatch"):
        launch_verified_agent(
            executable, metadata,
            runner=lambda *args, **kwargs: launches.append(args),
            require_windows=False,
        )
    assert launches == []


def test_agent_harness_rejects_invalid_metadata_digest(tmp_path):
    executable, metadata = write_fixture(tmp_path, b"agent")
    metadata.write_text(json.dumps({"size_bytes": 5, "sha256": "not-a-digest"}), encoding="utf-8")
    with pytest.raises(ValueError, match="valid SHA-256"):
        verify_agent(executable, metadata)


def test_agent_harness_launches_only_after_successful_verification(tmp_path):
    executable, metadata = write_fixture(tmp_path, b"verified-agent")
    launches = []

    def fake_runner(command, **kwargs):
        launches.append((command, kwargs))
        return "launched"

    result = launch_verified_agent(executable, metadata, runner=fake_runner, require_windows=False)
    assert result == "launched"
    assert launches == [([str(executable)], {"close_fds": True})]
