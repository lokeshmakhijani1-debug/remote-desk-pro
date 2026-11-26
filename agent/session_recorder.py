"""Explicitly consented MP4 session recorder with bounded retention and SHA-256 audit."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("remote-desk-agent")
RECORDING_DIR = Path.home() / "Videos" / "RemoteDeskPro-Recordings"


def cleanup_recordings(folder: Path = RECORDING_DIR, keep_last: int = 5, max_storage_mb: int = 1024) -> list[Path]:
    """Remove oldest completed MP4 files until both retention limits are met."""
    root = Path(folder).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    keep_last = max(1, min(int(keep_last), 100))
    max_bytes = max(100, min(int(max_storage_mb), 20480)) * 1024 * 1024
    files = sorted((p for p in root.glob("session_*.mp4") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    removed: list[Path] = []
    total = sum(p.stat().st_size for p in files)
    for index, path in enumerate(files):
        if index < keep_last and total <= max_bytes:
            continue
        size = path.stat().st_size
        path.unlink()
        total -= size
        removed.append(path)
    return removed


class SessionRecorder:
    def __init__(self, device_id: str, viewer_id: str, fps: int = 5,
                 max_duration_seconds: int = 1800, retention_count: int = 5,
                 max_storage_mb: int = 1024) -> None:
        safe_device = re.sub(r"[^0-9A-Za-z_-]", "_", str(device_id))[:64] or "device"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.folder = RECORDING_DIR
        self.path = self.folder / ("session_" + safe_device + "_" + stamp + ".mp4")
        self.audit_path = self.folder / "audit_log.jsonl"
        self.device_id = safe_device
        self.viewer_id = str(viewer_id)[:128]
        self.fps = max(1, min(int(fps), 10))
        self.max_duration_seconds = max(1, min(int(max_duration_seconds), 4 * 60 * 60))
        self.retention_count = max(1, min(int(retention_count), 100))
        self.max_storage_mb = max(100, min(int(max_storage_mb), 20480))
        self._stop = threading.Event()
        self._started = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None
        self.sha256: str | None = None
        self.started_monotonic: float | None = None

    @property
    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.is_alive:
            return
        cleanup_recordings(self.folder, self.retention_count, self.max_storage_mb)
        self._thread = threading.Thread(target=self._record, name="rdp-session-recorder", daemon=True)
        self._thread.start()
        if not self._started.wait(12):
            self.stop()
            raise TimeoutError("Session recorder startup timed out")
        if self._error:
            raise RuntimeError("Session recorder could not initialize") from self._error

    def _audit(self, event: str, **fields) -> None:
        record = {"event": event, "at": datetime.now(timezone.utc).isoformat(),
                  "device_id": self.device_id, "viewer_id": self.viewer_id,
                  "recording": self.path.name, **fields}
        with self.audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _record(self) -> None:
        writer = None
        try:
            import imageio_ffmpeg
            import mss
            with mss.mss() as capture:
                monitor = capture.monitors[1]
                width = int(monitor["width"]) & ~1
                height = int(monitor["height"]) & ~1
                if width < 2 or height < 2:
                    raise RuntimeError("Primary display dimensions are unavailable")
                writer = imageio_ffmpeg.write_frames(str(self.path), (width, height), fps=self.fps,
                    codec="libx264", pix_fmt_in="rgb24", pix_fmt_out="yuv420p", macro_block_size=2)
                writer.send(None)
                self.started_monotonic = time.monotonic()
                self._audit("session_started", started_at=datetime.now(timezone.utc).isoformat(),
                            max_duration_seconds=self.max_duration_seconds)
                self._started.set()
                while not self._stop.is_set():
                    if time.monotonic() - self.started_monotonic >= self.max_duration_seconds:
                        self._audit("session_auto_stopped", reason="maximum_duration")
                        self._stop.set()
                        break
                    frame = capture.grab(monitor)
                    rgb = frame.rgb
                    if len(rgb) != width * height * 3:
                        raise RuntimeError("Captured frame dimensions changed during recording")
                    writer.send(rgb)
                    self._stop.wait(1 / self.fps)
                writer.close()
                writer = None
            digest = hashlib.sha256()
            with self.path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            self.sha256 = digest.hexdigest()
            self._audit("session_ended", ended_at=datetime.now(timezone.utc).isoformat(),
                        sha256=self.sha256, size_bytes=self.path.stat().st_size)
            cleanup_recordings(self.folder, self.retention_count, self.max_storage_mb)
        except BaseException as exc:
            self._error = exc
            log.exception("Background session recording failed")
            self._started.set()
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=15)
            if self._thread.is_alive():
                raise TimeoutError("Session recorder did not finalize within 15 seconds")
        if self._error:
            raise RuntimeError("Session recording failed") from self._error
