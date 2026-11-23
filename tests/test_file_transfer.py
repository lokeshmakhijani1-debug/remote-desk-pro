from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from backend.file_transfer import (
    MIN_CHUNK_SIZE,
    ResumableTransferStore,
    TransferError,
    TransferManifest,
)


def test_resumable_chunks_finalize_atomically(tmp_path: Path) -> None:
    payload = b"A" * (MIN_CHUNK_SIZE + 17)
    transfer_id = "12345678-1234-5678-1234-567812345678"
    store = ResumableTransferStore(tmp_path, MIN_CHUNK_SIZE)
    manifest = TransferManifest(
        transfer_id, "payload.bin", len(payload), hashlib.sha256(payload).hexdigest(),
        MIN_CHUNK_SIZE, "none",
    )
    store.begin(manifest)
    first = payload[:MIN_CHUNK_SIZE]
    store.append(transfer_id, 0, first, "none", 0)
    resumed = ResumableTransferStore(tmp_path, MIN_CHUNK_SIZE)
    assert resumed.status(transfer_id)["next_missing_offset"] == MIN_CHUNK_SIZE
    resumed.append(transfer_id, MIN_CHUNK_SIZE, payload[MIN_CHUNK_SIZE:], "none", 1)
    destination = resumed.finalize(transfer_id)
    assert destination.read_bytes() == payload
    assert not (tmp_path / f"{transfer_id}.part").exists()


def test_conflicting_retransmission_is_rejected(tmp_path: Path) -> None:
    payload = b"B" * MIN_CHUNK_SIZE
    transfer_id = "12345678-1234-5678-1234-567812345679"
    store = ResumableTransferStore(tmp_path)
    store.begin(TransferManifest(
        transfer_id, "payload.bin", len(payload), hashlib.sha256(payload).hexdigest(),
        MIN_CHUNK_SIZE, "none",
    ))
    store.append(transfer_id, 0, payload, "none", 0)
    with pytest.raises(TransferError):
        store.append(transfer_id, 0, b"C" * MIN_CHUNK_SIZE, "none", 0)


def test_finalize_rejects_missing_chunks(tmp_path: Path) -> None:
    payload = b"C" * (MIN_CHUNK_SIZE + 1)
    transfer_id = "12345678-1234-5678-1234-567812345670"
    store = ResumableTransferStore(tmp_path)
    store.begin(TransferManifest(
        transfer_id, "payload.bin", len(payload), hashlib.sha256(payload).hexdigest(),
        MIN_CHUNK_SIZE, "none",
    ))
    with pytest.raises(TransferError):
        store.finalize(transfer_id)


def test_endpoint_receiver_persists_ack_and_verifies_sha256(tmp_path: Path) -> None:
    from agent.resumable_transfer import EndpointFileReceiver

    payload = b"R" * (MIN_CHUNK_SIZE + 9)
    destination = tmp_path / "received.bin"
    transfer_id = "12345678-1234-5678-1234-567812345681"
    receiver = EndpointFileReceiver(destination, transfer_id, len(payload),
                                    hashlib.sha256(payload).hexdigest(), MIN_CHUNK_SIZE, "none")
    assert receiver.append(0, payload[:MIN_CHUNK_SIZE], 0) == MIN_CHUNK_SIZE
    resumed = EndpointFileReceiver(destination, transfer_id, len(payload),
                                   hashlib.sha256(payload).hexdigest(), MIN_CHUNK_SIZE, "none")
    assert resumed.next_offset == MIN_CHUNK_SIZE
    assert resumed.append(MIN_CHUNK_SIZE, payload[MIN_CHUNK_SIZE:], 1) == len(payload)
    assert resumed.finalize().read_bytes() == payload


def test_endpoint_receiver_rejects_bad_final_checksum(tmp_path: Path) -> None:
    from agent.resumable_transfer import EndpointFileReceiver, EndpointTransferError

    payload = b"S" * MIN_CHUNK_SIZE
    receiver = EndpointFileReceiver(tmp_path / "bad.bin", "12345678-1234-5678-1234-567812345682",
                                    len(payload), "0" * 64, MIN_CHUNK_SIZE, "none")
    receiver.append(0, payload, 0)
    with pytest.raises(EndpointTransferError, match="SHA-256"):
        receiver.finalize()


def test_chunk_index_must_match_sequential_offset(tmp_path: Path) -> None:
    payload = b"I" * (MIN_CHUNK_SIZE + 5)
    transfer_id = "12345678-1234-5678-1234-567812345683"
    store = ResumableTransferStore(tmp_path)
    store.begin(TransferManifest(
        transfer_id, "indexed.bin", len(payload), hashlib.sha256(payload).hexdigest(),
        MIN_CHUNK_SIZE, "none",
    ))
    with pytest.raises(TransferError, match="sequential"):
        store.append(transfer_id, 0, payload[:MIN_CHUNK_SIZE], "none", 1)
    store.append(transfer_id, 0, payload[:MIN_CHUNK_SIZE], "none", 0)
    with pytest.raises(TransferError, match="sequential"):
        store.append(transfer_id, MIN_CHUNK_SIZE, payload[MIN_CHUNK_SIZE:], "none", 0)


def test_backend_store_rejects_a_gap_even_with_the_matching_later_index(tmp_path: Path) -> None:
    payload = b"G" * (MIN_CHUNK_SIZE * 2)
    transfer_id = "12345678-1234-5678-1234-567812345684"
    store = ResumableTransferStore(tmp_path)
    store.begin(TransferManifest(
        transfer_id, "gap.bin", len(payload), hashlib.sha256(payload).hexdigest(),
        MIN_CHUNK_SIZE, "none",
    ))
    with pytest.raises(TransferError, match="sequential"):
        store.append(transfer_id, MIN_CHUNK_SIZE, payload[MIN_CHUNK_SIZE:], "none", 1)


def test_endpoint_receiver_rejects_nonsequential_chunk_index(tmp_path: Path) -> None:
    from agent.resumable_transfer import EndpointFileReceiver, EndpointTransferError

    payload = b"E" * (MIN_CHUNK_SIZE + 1)
    receiver = EndpointFileReceiver(
        tmp_path / "endpoint-gap.bin", "12345678-1234-5678-1234-567812345685",
        len(payload), hashlib.sha256(payload).hexdigest(), MIN_CHUNK_SIZE, "none",
    )
    with pytest.raises(EndpointTransferError, match="sequential"):
        receiver.append(0, payload[:MIN_CHUNK_SIZE], 1)


def test_agent_chunk_ack_yields_twenty_milliseconds(monkeypatch):
    import asyncio
    import json
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
    import host_agent
    sent, delays = [], []
    class FakeSocket:
        async def send(self, value):
            sent.append(json.loads(value))
    async def fake_sleep(delay):
        delays.append(delay)
    monkeypatch.setattr(host_agent.asyncio, "sleep", fake_sleep)
    asyncio.run(host_agent.send_transfer_ack(FakeSocket(), "12345678-1234-5678-1234-567812345678", MIN_CHUNK_SIZE, MIN_CHUNK_SIZE))
    assert sent == [{"type":"transfer_ack", "transfer_id":"12345678-1234-5678-1234-567812345678",
                    "next_offset":MIN_CHUNK_SIZE, "next_index":1}]
    assert delays == [0.02]


def test_remote_clipboard_writes_do_not_echo_and_local_copies_publish_once():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
    import host_agent
    state = host_agent.ClipboardSyncState()
    state.last_seen = "initial host clipboard"
    state.begin_remote_write("text from dashboard")
    assert state.should_publish("initial host clipboard") is False
    assert state.should_publish("text from dashboard") is False
    assert state.should_publish("text from dashboard") is False
    assert state.should_publish("new Windows copy") is True
    assert state.should_publish("new Windows copy") is False


def test_websocket_frame_size_and_frontend_ack_pacing_are_configured():
    root = Path(__file__).resolve().parents[1]
    backend = (root / "backend" / "main.py").read_text(encoding="utf-8")
    local_runner = (root / "run_local_test.ps1").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    frontend = (root / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "WEBSOCKET_MAX_SIZE = 16 * 1024 * 1024" in backend
    assert "--ws-max-size" in local_runner and "16777216" in local_runner
    assert "--ws-max-size" in dockerfile and "16777216" in dockerfile
    assert "transferInFlight.current!==null" in frontend
    assert "setTimeout(resolve,20)" in frontend
    assert "clipboard_set" in frontend and "clipboard_paste" in frontend
