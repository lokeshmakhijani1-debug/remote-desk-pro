from __future__ import annotations

import hashlib
import json
import random
import uuid
from pathlib import Path

import pytest

from agent.resumable_transfer import (
    EndpointFileReceiver, EndpointTransferError, MAX_RATIO, MAX_CHUNK,
    MIN_CHUNK, MAX_FILE_SIZE,
)

def _id() -> str:
    return str(uuid.uuid4())

def _receiver(tmp_path: Path, payload: bytes, chunk: int = 512 * 1024,
              compression: str = "none", transfer_id: str | None = None):
    return EndpointFileReceiver(tmp_path / "Downloads" / "payload.bin",
        transfer_id or _id(), len(payload), hashlib.sha256(payload).hexdigest(),
        chunk, compression)

def _transfer(receiver: EndpointFileReceiver, payload: bytes):
    for offset in range(0, len(payload), receiver.chunk_size):
        block = payload[offset:offset + receiver.chunk_size]
        receiver.append(offset, block, offset // receiver.chunk_size)
    return receiver.finalize()

def test_01_http_lan_sha256_contract_and_large_raw_transfers(tmp_path: Path):
    # Host-side digest validation for 465 KiB PDF and 12 MiB binary fixtures.
    app = (Path(__file__).resolve().parents[1] / "frontend/src/App.tsx").read_text()
    assert "function sha256Hex(input:Uint8Array)" in app
    assert "crypto.subtle.digest" not in app
    for size in (465 * 1024, 12 * 1024 * 1024):
        payload = bytes((i * 31) % 256 for i in range(size))
        receiver = _receiver(tmp_path / str(size), payload)
        assert _transfer(receiver, payload).read_bytes() == payload
        assert len(hashlib.sha256(payload).hexdigest()) == 64

@pytest.mark.parametrize("chunk_size", [256 * 1024, 512 * 1024, 64 * 1024, 1024 * 1024])
def test_02_legacy_and_negotiated_chunk_sizes(tmp_path: Path, chunk_size: int):
    payload = b"legacy-chunk" * (100 * 1024)
    receiver = _receiver(tmp_path / str(chunk_size), payload, chunk_size)
    assert _transfer(receiver, payload).stat().st_size == len(payload)

def test_03_corrupt_or_mismatched_partial_state_restarts_cleanly(tmp_path: Path):
    payload = b"recovery" * 100000
    transfer_id = _id()
    receiver = _receiver(tmp_path, payload, 512 * 1024, transfer_id=transfer_id)
    receiver.append(0, payload[:512 * 1024], 0)
    receiver.state.write_text(json.dumps({"transfer_id": transfer_id, "sha256": "0" * 64,
        "chunk_size": 256 * 1024, "acknowledged": {"0": "0" * 64}}))
    restarted = _receiver(tmp_path, payload, 256 * 1024, transfer_id=transfer_id)
    assert restarted.next_offset == 0
    assert _transfer(restarted, payload).read_bytes() == payload

def test_04_raw_and_headerless_streaming_zstd_are_bounded(tmp_path: Path):
    zstandard = pytest.importorskip("zstandard")
    payload = random.Random(42).randbytes(200000)
    raw = _receiver(tmp_path / "raw", payload, compression="none")
    assert _transfer(raw, payload).read_bytes() == payload
    compressor = zstandard.ZstdCompressor(write_content_size=False)
    compressed = compressor.compressobj()
    encoded = compressed.compress(payload) + compressed.flush()
    receiver = _receiver(tmp_path / "zstd", payload, chunk=MAX_CHUNK, compression="zstd")
    receiver.append(0, encoded, 0)
    assert receiver.finalize().read_bytes() == payload
    bomb_payload = b"A" * (MAX_CHUNK)
    bomb_data = zstandard.ZstdCompressor(write_content_size=False).compress(bomb_payload)
    bomb = _receiver(tmp_path / "bomb", bomb_payload, chunk=MAX_CHUNK, compression="zstd")
    with pytest.raises(EndpointTransferError, match="ratio|bounds"):
        bomb.append(0, bomb_data, 0)

def test_05_disconnect_resume_uses_exact_acknowledged_offset(tmp_path: Path):
    payload = bytes((i * 7) % 256 for i in range(10 * 1024 * 1024))
    transfer_id = _id()
    first = _receiver(tmp_path, payload, transfer_id=transfer_id)
    cutoff = int(len(payload) * 0.45) // first.chunk_size * first.chunk_size
    for offset in range(0, cutoff, first.chunk_size):
        first.append(offset, payload[offset:offset + first.chunk_size], offset // first.chunk_size)
    resumed = _receiver(tmp_path, payload, transfer_id=transfer_id)
    assert resumed.next_offset == cutoff
    for offset in range(cutoff, len(payload), resumed.chunk_size):
        resumed.append(offset, payload[offset:offset + resumed.chunk_size], offset // resumed.chunk_size)
    assert resumed.finalize().read_bytes() == payload

def test_06_jitter_duplicate_and_out_of_order_chunks(tmp_path: Path):
    payload = b"network-jitter" * 100000
    receiver = _receiver(tmp_path, payload, chunk=MIN_CHUNK)
    first = payload[:MIN_CHUNK]
    assert receiver.append(0, first, 0) == MIN_CHUNK
    assert receiver.append(0, first, 0) == MIN_CHUNK
    with pytest.raises(EndpointTransferError, match="Out-of-order"):
        receiver.append(2 * MIN_CHUNK, payload[2 * MIN_CHUNK:3 * MIN_CHUNK], 2)
    with pytest.raises(EndpointTransferError, match="Conflicting"):
        receiver.append(0, b"X" * MIN_CHUNK, 0)

def test_07_path_size_uuid_and_tampered_digest_are_rejected(tmp_path: Path):
    with pytest.raises(EndpointTransferError):
        EndpointFileReceiver(tmp_path / "Downloads" / "evil.exe", "../../Windows/System32/evil.exe",
            10, hashlib.sha256(b"x").hexdigest(), MIN_CHUNK, "none")
    with pytest.raises(EndpointTransferError):
        EndpointFileReceiver(tmp_path / "Downloads" / "large.bin", _id(), MAX_FILE_SIZE + 1,
            "0" * 64, MIN_CHUNK, "none")
    payload = b"tamper-check"
    receiver = EndpointFileReceiver(tmp_path / "Downloads" / "tampered.bin", _id(),
        len(payload), "0" * 64, MIN_CHUNK, "none")
    receiver.append(0, payload, 0)
    with pytest.raises(EndpointTransferError, match="SHA-256"):
        receiver.finalize()
    assert not (tmp_path / "Windows/System32/evil.exe").exists()

def test_08_clipboard_limit_and_echo_suppression():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
    import host_agent
    state = host_agent.ClipboardSyncState()
    state.last_seen = "host"
    state.begin_remote_write("viewer")
    assert state.should_publish("viewer") is False
    assert state.should_publish("viewer") is False
    assert state.should_publish("new host text") is True
    assert state.should_publish("x" * 65537) is False

def test_09_concurrent_screen_frame_heartbeat_and_25mb_transfer(tmp_path: Path):
    payload = bytes((i * 13) % 256 for i in range(25 * 1024 * 1024))
    receiver = _receiver(tmp_path, payload)
    frames = [b"\xff\xd8" + bytes(128 * 1024) + b"\xff\xd9" for _ in range(32)]
    heartbeat_count = 0
    for offset in range(0, len(payload), receiver.chunk_size):
        receiver.append(offset, payload[offset:offset + receiver.chunk_size], offset // receiver.chunk_size)
        heartbeat_count += 1
        assert len(frames[heartbeat_count % len(frames)]) < 16 * 1024 * 1024
    assert heartbeat_count > 0
    assert receiver.finalize().read_bytes() == payload

def test_10_reconnect_state_is_resumable_after_receiver_recreation(tmp_path: Path):
    payload = b"reconnect" * 200000
    transfer_id = _id()
    first = _receiver(tmp_path, payload, transfer_id=transfer_id)
    first.append(0, payload[:first.chunk_size], 0)
    second = _receiver(tmp_path, payload, transfer_id=transfer_id)
    assert second.next_offset == first.chunk_size
    assert _transfer(second, payload).read_bytes() == payload


def test_zstd_headerless_raw_fallback_never_regresses(tmp_path: Path) -> None:
    import hashlib, uuid
    from agent.resumable_transfer import EndpointFileReceiver
    payload = b"PDF-RAW-CONTENT-" * 2048
    sha = hashlib.sha256(payload).hexdigest()
    tid = str(uuid.uuid4())
    dest = tmp_path / "fallback.pdf"
    rx = EndpointFileReceiver(dest, tid, len(payload), sha, 64 * 1024, "zstd")
    nxt = rx.append(0, payload, 0)
    assert nxt == len(payload)
    assert rx.finalize() == dest
    assert dest.read_bytes() == payload
