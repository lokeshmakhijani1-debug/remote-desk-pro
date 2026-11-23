"""Durable chunk storage primitives for resumable, integrity-checked transfers."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CHUNK_SIZE = 512 * 1024
MIN_CHUNK_SIZE = CHUNK_SIZE
MAX_CHUNK_SIZE = CHUNK_SIZE
MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_EXPANSION_RATIO = 100
_TRANSFER_ID = re.compile(r"^[a-fA-F0-9-]{16,64}$")
_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")


class TransferError(ValueError):
    """Raised when a transfer violates protocol or integrity constraints."""


@dataclass(frozen=True, slots=True)
class TransferManifest:
    transfer_id: str
    file_name: str
    total_size: int
    expected_sha256: str
    chunk_size: int
    compression: str


class ResumableTransferStore:
    """Persist acknowledged chunks and atomically finalize verified files."""

    def __init__(self, root: Path, chunk_size: int = MIN_CHUNK_SIZE) -> None:
        if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
            raise TransferError("Chunk size must be between 256 KiB and 1 MiB")
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.chunk_size = chunk_size

    @staticmethod
    def _safe_id(transfer_id: str) -> str:
        if not _TRANSFER_ID.fullmatch(transfer_id):
            raise TransferError("Invalid transfer ID")
        return transfer_id.lower()

    @staticmethod
    def _safe_name(file_name: str) -> str:
        name = Path(str(file_name).replace("\\", "/")).name
        if not name or name in {".", ".."} or len(name) > 180 or "\x00" in name:
            raise TransferError("Invalid file name")
        return name

    def _paths(self, transfer_id: str) -> tuple[Path, Path]:
        safe_id = self._safe_id(transfer_id)
        return self.root / f"{safe_id}.part", self.root / f"{safe_id}.json"

    @staticmethod
    def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
        fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, separators=(",", ":"), sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def begin(self, manifest: TransferManifest) -> dict[str, Any]:
        transfer_id = self._safe_id(manifest.transfer_id)
        name = self._safe_name(manifest.file_name)
        if not 0 < manifest.total_size <= MAX_FILE_SIZE:
            raise TransferError("File size exceeds transfer limits")
        if not _SHA256.fullmatch(manifest.expected_sha256):
            raise TransferError("Expected SHA-256 must be 64 hexadecimal characters")
        if manifest.chunk_size != self.chunk_size:
            raise TransferError("Manifest chunk size does not match this store")
        if manifest.compression not in {"none", "zstd"}:
            raise TransferError("Unsupported compression mode")
        part, state = self._paths(transfer_id)
        if state.exists():
            existing = self._load(state)
            expected = asdict(manifest)
            expected["transfer_id"] = transfer_id
            expected["file_name"] = name
            if existing["manifest"] != expected:
                raise TransferError("Transfer ID is already bound to another manifest")
            if not part.exists():
                raise TransferError("Transfer state exists without its partial file")
            return self.status(transfer_id)
        with part.open("xb") as handle:
            handle.truncate(manifest.total_size)
            handle.flush()
            os.fsync(handle.fileno())
        self._write_json_atomic(state, {
            "manifest": {**asdict(manifest), "transfer_id": transfer_id, "file_name": name},
            "acknowledged": {},
        })
        return self.status(transfer_id)

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TransferError("Transfer state is unreadable") from exc
        if not isinstance(value, dict) or not isinstance(value.get("acknowledged"), dict):
            raise TransferError("Transfer state is malformed")
        return value

    @staticmethod
    def _decode(payload: bytes, compression: str, maximum: int) -> bytes:
        if compression == "none":
            decoded = payload
        elif compression == "zstd":
            try:
                import zstandard
                params = zstandard.get_frame_parameters(payload)
                declared = params.content_size
                if declared not in (zstandard.CONTENTSIZE_UNKNOWN, zstandard.CONTENTSIZE_ERROR):
                    if declared > maximum or declared > max(1, len(payload)) * MAX_EXPANSION_RATIO:
                        raise TransferError("Compressed chunk exceeds expansion limits")
                decoded = zstandard.ZstdDecompressor().decompress(payload, max_output_size=maximum)
            except TransferError:
                raise
            except Exception as exc:
                raise TransferError("Invalid or oversized Zstandard chunk") from exc
        else:
            raise TransferError("Unsupported compression mode")
        if len(decoded) > maximum or len(decoded) > max(1, len(payload)) * MAX_EXPANSION_RATIO:
            raise TransferError("Chunk exceeds decompressed size or ratio limits")
        return decoded

    def append(self, transfer_id: str, offset: int, payload: bytes, compression: str, chunk_index: int) -> dict[str, Any]:
        part, state_path = self._paths(transfer_id)
        state = self._load(state_path)
        manifest = state["manifest"]
        if compression != manifest["compression"]:
            raise TransferError("Chunk compression does not match transfer manifest")
        if not isinstance(offset, int) or offset < 0 or offset >= manifest["total_size"]:
            raise TransferError("Invalid chunk offset")
        if offset % manifest["chunk_size"]:
            raise TransferError("Chunk offset is not aligned")
        if chunk_index != offset // manifest["chunk_size"]:
            raise TransferError("Chunk index is not the next sequential index")
        decoded = self._decode(payload, compression, manifest["chunk_size"])
        expected_length = min(manifest["chunk_size"], manifest["total_size"] - offset)
        if len(decoded) != expected_length:
            raise TransferError("Chunk length does not match its expected range")
        key = str(offset)
        next_missing = self.status(transfer_id)["next_missing_offset"]
        if offset != next_missing and key not in state["acknowledged"]:
            raise TransferError("Chunk index is not the next sequential index")
        digest = hashlib.sha256(decoded).hexdigest()
        prior = state["acknowledged"].get(key)
        if prior:
            if prior != digest:
                raise TransferError("Conflicting retransmission for acknowledged chunk")
            return self.status(transfer_id)
        with part.open("r+b") as handle:
            handle.seek(offset)
            handle.write(decoded)
            handle.flush()
            os.fsync(handle.fileno())
        state["acknowledged"][key] = digest
        self._write_json_atomic(state_path, state)
        return self.status(transfer_id)

    def status(self, transfer_id: str) -> dict[str, Any]:
        _, state_path = self._paths(transfer_id)
        state = self._load(state_path)
        manifest = state["manifest"]
        offsets = sorted(int(value) for value in state["acknowledged"])
        total_chunks = (manifest["total_size"] + manifest["chunk_size"] - 1) // manifest["chunk_size"]
        return {
            "transfer_id": manifest["transfer_id"],
            "acknowledged_offsets": offsets,
            "next_missing_offset": next(
                (index * manifest["chunk_size"] for index in range(total_chunks)
                 if str(index * manifest["chunk_size"]) not in state["acknowledged"]),
                manifest["total_size"],
            ),
            "acknowledged_chunks": len(offsets),
            "total_chunks": total_chunks,
        }

    def finalize(self, transfer_id: str) -> Path:
        part, state_path = self._paths(transfer_id)
        state = self._load(state_path)
        manifest = state["manifest"]
        status = self.status(transfer_id)
        if status["acknowledged_chunks"] != status["total_chunks"]:
            raise TransferError("Cannot finalize an incomplete transfer")
        digest = hashlib.sha256()
        with part.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest().lower() != manifest["expected_sha256"].lower():
            raise TransferError("Final SHA-256 verification failed")
        destination = self.root / manifest["file_name"]
        if destination.exists():
            raise TransferError("Destination file already exists")
        os.replace(part, destination)
        state_path.unlink(missing_ok=True)
        return destination

    def cancel(self, transfer_id: str) -> None:
        part, state = self._paths(transfer_id)
        part.unlink(missing_ok=True)
        state.unlink(missing_ok=True)
