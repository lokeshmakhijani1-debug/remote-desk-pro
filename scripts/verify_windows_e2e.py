"""Verify the published Windows agent SHA-256 before any optional execution."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Callable, Any


def verify_agent(executable: Path, metadata_file: Path) -> dict[str, Any]:
    metadata = json.loads(metadata_file.read_text(encoding="utf-8-sig"))
    expected_hash = str(metadata.get("sha256", "")).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise ValueError("Build metadata must contain a valid SHA-256 digest")
    if not executable.is_file():
        raise FileNotFoundError(f"Windows agent executable not found: {executable}")
    expected_size = metadata.get("size_bytes")
    actual_size = executable.stat().st_size
    if type(expected_size) is not int or actual_size != expected_size:
        raise ValueError(f"Agent size mismatch: expected={expected_size}, actual={actual_size}")

    digest = hashlib.sha256()
    with executable.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    actual_hash = digest.hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(f"Agent SHA-256 mismatch: expected={expected_hash}, actual={actual_hash}")
    return {"path": str(executable), "size_bytes": actual_size, "sha256": actual_hash}


def launch_verified_agent(
    executable: Path,
    metadata_file: Path,
    *,
    runner: Callable[..., Any] | None = None,
    require_windows: bool = True,
) -> Any:
    verified = verify_agent(executable, metadata_file)
    if require_windows and os.name != "nt":
        raise OSError("Agent execution is supported only on Windows")
    launch = runner or subprocess.Popen
    return launch([str(executable)], close_fds=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=Path("backend/downloads/RemoteDeskPro-Agent.exe"))
    parser.add_argument("--metadata", type=Path, default=Path("backend/downloads/agent-build.json"))
    parser.add_argument("--execute", action="store_true", help="Launch the verified GUI agent (Windows only)")
    args = parser.parse_args()
    verified = verify_agent(args.exe, args.metadata)
    print(json.dumps({"status": "sha256_verified", **verified}, indent=2))
    if args.execute:
        process = launch_verified_agent(args.exe, args.metadata)
        print(json.dumps({"status": "launched", "pid": process.pid}, indent=2))
    else:
        print("Verification only. Pass --execute on Windows to launch the verified GUI agent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
