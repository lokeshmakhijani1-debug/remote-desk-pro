"""Endpoint-local resumable file receiver with bounded decompression and SHA-256 checks."""
from __future__ import annotations

import hashlib
import json
import os
import re
import zlib
from io import BytesIO
from pathlib import Path
from typing import Any

MAX_FILE_SIZE = 50 * 1024 * 1024
CHUNK_SIZE = 512 * 1024
MIN_CHUNK = 64 * 1024
MAX_CHUNK = 1024 * 1024
MAX_RATIO = 100
_ID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
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
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        self.part = self.destination.with_name(self.destination.name + "." + transfer_id + ".part")
        self.state = self.part.with_suffix(self.part.suffix + ".json")
        self.transfer_id = transfer_id
        self.total_size = total_size
        self.expected_sha256 = expected_sha256.lower()
        self.chunk_size = chunk_size
        self.compression = compression
        self.acknowledged: dict[str, str] = {}
        saved = None
        if self.state.exists():
            try:
                saved = json.loads(self.state.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                saved = None
        compatible = bool(isinstance(saved, dict) and saved.get("transfer_id") == transfer_id
                          and saved.get("sha256") == self.expected_sha256
                          and saved.get("total_size") == total_size
                          and saved.get("chunk_size") == chunk_size
                          and saved.get("compression", "none") == compression
                          and self.part.exists())
        if compatible:
            try:
                acknowledged = saved.get("acknowledged", {})
                if not isinstance(acknowledged, dict):
                    raise ValueError("Invalid acknowledgement map")
                self.acknowledged = dict(acknowledged)
            except (TypeError, ValueError):
                compatible = False
            if compatible and any(not str(k).isdigit() or not isinstance(v, str) or not _SHA.fullmatch(v)
                   for k, v in self.acknowledged.items()):
                compatible = False
        if not compatible:
            self.part.unlink(missing_ok=True)
            self.state.unlink(missing_ok=True)
            self.acknowledged = {}
            with self.part.open("wb") as stream:
                stream.truncate(total_size)
                stream.flush()
                os.fsync(stream.fileno())
            self._save()

    def _save(self) -> None:
        temporary = self.state.with_suffix(self.state.suffix + ".tmp")
        temporary.write_text(json.dumps({"transfer_id": self.transfer_id, "sha256": self.expected_sha256,
                                         "acknowledged": self.acknowledged, "total_size": self.total_size,
                                         "chunk_size": self.chunk_size, "compression": self.compression}), encoding="utf-8")
        os.replace(temporary, self.state)

    @property
    def next_offset(self) -> int:
        offset = 0
        while str(offset) in self.acknowledged:
            offset += min(self.chunk_size, self.total_size - offset)
        return offset

    def append(self, offset: int, encoded: bytes, chunk_index: int) -> int:
        if not isinstance(offset, int) or offset < 0 or offset >= self.total_size:
            raise EndpointTransferError("Invalid chunk offset")
        expected_index = offset // self.chunk_size
        if chunk_index < 0:
            chunk_index = expected_index
        if chunk_index != expected_index or offset != expected_index * self.chunk_size:
            raise EndpointTransferError(f"Chunk index is not the next sequential index (got={chunk_index}, expected={expected_index}, offset={offset}, chunk_size={self.chunk_size})")
        limit = min(self.chunk_size, self.total_size - offset)
        if self.compression == "zstd":
            decoded = None
            try:
                import zstandard
                decoder = zstandard.ZstdDecompressor()
                try:
                    with decoder.stream_reader(BytesIO(encoded), read_size=64 * 1024) as reader:
                        decoded = reader.read(MAX_CHUNK + 1)
                        if len(decoded) > MAX_CHUNK:
                            decoded = None
                except Exception:
                    decoded = decoder.decompress(encoded, max_output_size=MAX_CHUNK)
            except Exception:
                decoded = None
            if decoded is None:
                for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
                    try:
                        decoded = zlib.decompress(encoded, wbits)
                        break
                    except Exception:
                        pass
            if decoded is None:
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
            raise EndpointTransferError(f"Final SHA-256 mismatch (actual={digest.hexdigest()[:12]} expected={self.expected_sha256[:12]})")
        os.replace(self.part, self.destination)
        self.state.unlink(missing_ok=True)
        return self.destination
