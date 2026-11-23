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
