"""Endpoint-local resumable file receiver with bounded decompression and SHA-256 checks."""
from __future__ import annotations

import hashlib
import json
import os
import re
import zlib
from pathlib import Path
from typing import Any

MAX_FILE_SIZE = 50 * 1024 * 1024
MIN_CHUNK = 256 * 1024
MAX_CHUNK = 1024 * 1024
MAX_RATIO = 100
_ID = re.compile(r"^[0-9a-fA-F-]{16,64}$")
_SHA = re.compile(r"^[0-9a-fA-F]{64}$")


class EndpointTransferError(ValueError):
    """Invalid transfer metadata, chunk sequence, or integrity result."""


class EndpointFileReceiver:
    """Persist partial bytes and resume offset beside the user-selected destination."""

    def __init__(self, destination: Path, transfer_id: str, total_size: int,
                 expected_sha256: str, chunk_size: int, compression: str) -> None:
        if not _ID.fullmatch(transfer_id) or not 0 < total_size <= MAX_FILE_SIZE:
            raise EndpointTransferError("Invalid transfer identity or size")
        if not _SHA.fullmatch(expected_sha256) or not MIN_CHUNK <= chunk_size <= MAX_CHUNK:
            raise EndpointTransferError("Invalid checksum or chunk size")
        if compression not in {"none", "zstd"}:
            raise EndpointTransferError("Unsupported compression")
        self.destination = destination.resolve()
        self.part = self.destination.with_name(self.destination.name + "." + transfer_id + ".part")
        self.state = self.part.with_suffix(self.part.suffix + ".json")
        self.transfer_id = transfer_id
        self.total_size = total_size
        self.expected_sha256 = expected_sha256.lower()
        self.chunk_size = chunk_size
        self.compression = compression
        self.acknowledged: dict[str, str] = {}
        if self.state.exists():
            saved = json.loads(self.state.read_text(encoding="utf-8"))
            if saved.get("transfer_id") != transfer_id or saved.get("sha256") != self.expected_sha256:
                raise EndpointTransferError("Resume state does not match transfer")
            self.acknowledged = dict(saved.get("acknowledged", {}))
            if not self.part.exists():
                raise EndpointTransferError("Partial file is missing")
        else:
            with self.part.open("xb") as stream:
                stream.truncate(total_size)
                stream.flush()
                os.fsync(stream.fileno())
            self._save()

    def _save(self) -> None:
        temporary = self.state.with_suffix(self.state.suffix + ".tmp")
        temporary.write_text(json.dumps({"transfer_id": self.transfer_id, "sha256": self.expected_sha256,
                                         "acknowledged": self.acknowledged}), encoding="utf-8")
        os.replace(temporary, self.state)

    @property
    def next_offset(self) -> int:
        offset = 0
        while str(offset) in self.acknowledged:
            offset += min(self.chunk_size, self.total_size - offset)
        return offset

    def append(self, offset: int, encoded: bytes) -> int:
        if not isinstance(offset, int) or offset < 0 or offset >= self.total_size:
            raise EndpointTransferError("Invalid chunk offset")
        limit = min(self.chunk_size, self.total_size - offset)
        if self.compression == "zstd":
            try:
                import zstandard
                decoder = zstandard.ZstdDecompressor()
                decoded = decoder.decompress(encoded, max_output_size=limit)
            except Exception as exc:
                raise EndpointTransferError("Invalid or oversized Zstandard frame") from exc
            if len(decoded) > max(1, len(encoded)) * MAX_RATIO:
                raise EndpointTransferError("Compression expansion ratio exceeded")
        else:
            decoded = encoded
        if not decoded or len(decoded) > limit or offset + len(decoded) > self.total_size:
            raise EndpointTransferError("Chunk length exceeds transfer bounds")
        digest = hashlib.sha256(decoded).hexdigest()
        key = str(offset)
        if key in self.acknowledged:
            if self.acknowledged[key] != digest:
                raise EndpointTransferError("Conflicting retransmission")
            return self.next_offset
        if offset != self.next_offset:
            raise EndpointTransferError("Out-of-order chunk; request the acknowledged offset")
        with self.part.open("r+b") as stream:
            stream.seek(offset)
            stream.write(decoded)
            stream.flush()
            os.fsync(stream.fileno())
        self.acknowledged[key] = digest
        self._save()
        return self.next_offset

    def finalize(self) -> Path:
        if self.next_offset != self.total_size:
            raise EndpointTransferError("Transfer is incomplete")
        digest = hashlib.sha256()
        with self.part.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != self.expected_sha256:
            raise EndpointTransferError("Final SHA-256 mismatch")
        os.replace(self.part, self.destination)
        self.state.unlink(missing_ok=True)
        return self.destination
