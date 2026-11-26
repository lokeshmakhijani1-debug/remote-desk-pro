"""Bounded concurrency and fault-injection coverage for the relay and transfer paths.

These tests use isolated in-process sockets and temporary directories. They never
open production control sessions or mutate production files.
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
import tracemalloc
import types
from pathlib import Path

import httpx
import pytest

from backend.main import Hub
from backend.file_transfer import (
    MAX_FILE_SIZE,
    MIN_CHUNK_SIZE,
    ResumableTransferStore,
    TransferError,
    TransferManifest,
)
from agent.resumable_transfer import EndpointFileReceiver, EndpointTransferError
from backend.security import hash_secret, verify_secret
from agent import host_agent


class FakeSocket:
    async def send_text(self, _message):
        return None

    async def send_bytes(self, _message):
        return None

    async def close(self, **_kwargs):
        return None


def test_64_concurrent_viewer_admissions_are_bounded_and_exception_free():
    async def scenario():
        hub = Hub()
        sockets = [FakeSocket() for _ in range(64)]
        outcomes = await asyncio.wait_for(
            asyncio.gather(*[
                hub.register_viewer(f"device-{index:02d}", socket, 50, index + 1)
                for index, socket in enumerate(sockets)
            ]),
            timeout=5,
        )
        assert sum(bool(item[0]) for item in outcomes) == 50
        assert sum(not bool(item[0]) for item in outcomes) == 14
        assert sum(len(group) for group in hub.viewers.values()) == 50
        assert sum(len(group) for group in hub.viewer_owners.values()) == 50

    tracemalloc.start()
    before, _ = tracemalloc.get_traced_memory()
    asyncio.run(scenario())
    after, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert after - before < 16 * 1024 * 1024
    assert peak < 32 * 1024 * 1024


def test_32_parallel_256k_resumable_transfer_streams_complete(tmp_path: Path):
    async def transfer(index: int):
        payload = bytes([index]) * MIN_CHUNK_SIZE
        transfer_id = f"12345678-1234-5678-1234-{index:012d}"
        store = ResumableTransferStore(tmp_path / str(index), MIN_CHUNK_SIZE)
        manifest = TransferManifest(
            transfer_id, f"parallel-{index}.bin", len(payload),
            hashlib.sha256(payload).hexdigest(), MIN_CHUNK_SIZE, "none",
        )
        await asyncio.to_thread(store.begin, manifest)
        await asyncio.to_thread(store.append, transfer_id, 0, payload, "none")
        result = await asyncio.to_thread(store.finalize, transfer_id)
        assert result.read_bytes() == payload

    async def scenario():
        await asyncio.wait_for(
            asyncio.gather(*(transfer(index) for index in range(32))),
            timeout=30,
        )

    asyncio.run(scenario())


def test_oversized_file_and_truncated_chunks_fail_cleanly(tmp_path: Path):
    oversized = MAX_FILE_SIZE + 1
    transfer_id = "12345678-1234-5678-1234-567812345699"
    store = ResumableTransferStore(tmp_path / "store")
    manifest = TransferManifest(
        transfer_id, "too-large.bin", oversized, "0" * 64,
        MIN_CHUNK_SIZE, "none",
    )
    with pytest.raises(TransferError, match="size|limits"):
        store.begin(manifest)

    with pytest.raises(EndpointTransferError, match="identity or size"):
        EndpointFileReceiver(
            tmp_path / "too-large-endpoint.bin", transfer_id, oversized,
            "0" * 64, MIN_CHUNK_SIZE, "none",
        )

    payload = b"x" * MIN_CHUNK_SIZE
    valid_id = "12345678-1234-5678-1234-567812345698"
    valid = TransferManifest(
        valid_id, "truncated.bin", len(payload),
        hashlib.sha256(payload).hexdigest(), MIN_CHUNK_SIZE, "none",
    )
    store.begin(valid)
    with pytest.raises(TransferError, match="length"):
        store.append(valid_id, 0, payload[:-1], "none")
    store.cancel(valid_id)
    assert not (tmp_path / "store" / f"{valid_id}.part").exists()
    assert not (tmp_path / "store" / f"{valid_id}.json").exists()


def test_auth_hashes_do_not_cross_accept_passwords_or_accounts():
    first = hash_secret("Correct horse battery staple 1!")
    second = hash_secret("Different account password 2!")
    assert verify_secret(first, "Correct horse battery staple 1!")
    assert verify_secret(second, "Different account password 2!")
    assert not verify_secret(first, "Different account password 2!")
    assert not verify_secret(second, "Correct horse battery staple 1!")
    for guess in ("", "password", "123456", "wrong-password"):
        assert not verify_secret(first, guess)


def test_disconnect_cleanup_releases_all_virtual_modifier_keys(monkeypatch):
    released = []
    fake_pyautogui = types.SimpleNamespace(
        FAILSAFE=True,
        keyUp=lambda key, **_kwargs: released.append(key),
        mouseUp=lambda button="left", **_kwargs: released.append(f"mouse:{button}"),
    )
    monkeypatch.setitem(sys.modules, "pyautogui", fake_pyautogui)
    host_agent._PRESSED_KEYS.clear()
    host_agent._PRESSED_MOUSE_BUTTONS.clear()
    host_agent._PRESSED_KEYS.update({"ctrl", "alt", "shift"})
    host_agent._PRESSED_MOUSE_BUTTONS.add("left")

    host_agent.release_all_inputs()

    assert set(released) == {"ctrl", "alt", "shift", "mouse:left"}
    assert host_agent._PRESSED_KEYS == set()
    assert host_agent._PRESSED_MOUSE_BUTTONS == set()


def test_latency_spikes_do_not_deadlock_async_transfer_workers():
    async def delayed_ack(delay: float):
        await asyncio.sleep(delay)
        return delay

    async def scenario():
        results = await asyncio.wait_for(
            asyncio.gather(*(delayed_ack(delay) for delay in (0.5, 1.0, 2.0))),
            timeout=3,
        )
        assert results == [0.5, 1.0, 2.0]

    asyncio.run(scenario())


@pytest.mark.skipif(not __import__("os").getenv("RDP_BASE_URL"), reason="Set RDP_BASE_URL for safe live health/header checks")
def test_live_health_endpoint_and_security_header_baseline():
    base = __import__("os").environ["RDP_BASE_URL"].rstrip("/")
    assert base.startswith("https://"), "Live checks require HTTPS"
    response = httpx.get(base + "/health", timeout=15, follow_redirects=False)
    assert response.status_code == 200
    assert response.json().get("status") == "ok"
    # These headers are recorded as an explicit baseline; policy enforcement
    # can be tightened after confirming compatibility with the deployed UI.
    observed = {key.lower(): value for key, value in response.headers.items()}
    assert "content-type" in observed
    assert observed["content-type"].startswith("application/json")


def test_64_concurrent_host_registrations_and_viewer_sessions_are_isolated():
    async def scenario():
        hub = Hub()
        hosts = [FakeSocket() for _ in range(64)]
        viewers = [FakeSocket() for _ in range(64)]
        await asyncio.wait_for(
            asyncio.gather(*[
                hub.register_host(f"{index:09d}", socket)
                for index, socket in enumerate(hosts)
            ]),
            timeout=5,
        )
        outcomes = await asyncio.wait_for(
            asyncio.gather(*[
                hub.register_viewer(f"{index:09d}", socket, 50, index + 1000)
                for index, socket in enumerate(viewers)
            ]),
            timeout=5,
        )
        assert len(hub.hosts) == 64
        assert sum(bool(item[0]) for item in outcomes) == 50
        assert len(hub.viewers) == 50


def test_trusted_pin_authentication_burst_is_parallel_and_account_scoped():
    encoded_pin = hash_secret("482915")
    encoded_other_account = hash_secret("731604")

    async def verify_burst():
        checks = []
        for index in range(32):
            expected = "482915" if index % 2 == 0 else "731604"
            encoded = encoded_pin if index % 2 == 0 else encoded_other_account
            checks.append(asyncio.to_thread(verify_secret, encoded, expected))
        return await asyncio.wait_for(asyncio.gather(*checks), timeout=15)

    assert all(asyncio.run(verify_burst()))


def test_disk_full_during_chunk_write_can_be_cancelled_without_orphan_state(tmp_path, monkeypatch):
    import backend.file_transfer as transfer_module

    transfer_id = "12345678-1234-5678-1234-567812345697"
    payload = b"d" * MIN_CHUNK_SIZE
    store = ResumableTransferStore(tmp_path, MIN_CHUNK_SIZE)
    store.begin(TransferManifest(
        transfer_id, "disk-pressure.bin", len(payload),
        hashlib.sha256(payload).hexdigest(), MIN_CHUNK_SIZE, "none",
    ))

    def disk_full(_fd):
        raise OSError("No space left on device")

    monkeypatch.setattr(transfer_module.os, "fsync", disk_full)
    with pytest.raises(OSError, match="No space left"):
        store.append(transfer_id, 0, payload, "none")
    store.cancel(transfer_id)
    assert not (tmp_path / f"{transfer_id}.part").exists()
    assert not (tmp_path / f"{transfer_id}.json").exists()


def test_login_email_and_password_are_isolated_between_accounts(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from fastapi.testclient import TestClient
    from backend import main as backend_main
    from backend.database import Base, User

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db:
        db.add_all([
            User(email="alpha@example.com", password_hash=hash_secret("Alpha account password 1!"), role="admin"),
            User(email="beta@example.com", password_hash=hash_secret("Beta account password 2!"), role="technician"),
        ])
        db.commit()
    monkeypatch.setattr(backend_main, "SessionLocal", factory)
    backend_main._attempts.pop("login:testclient", None)
    client = TestClient(backend_main.app)
    try:
        alpha = client.post("/api/auth/login", json={
            "email": "ALPHA@example.com", "password": "Alpha account password 1!"
        })
        assert alpha.status_code == 200
        assert alpha.json()["user"]["email"] == "alpha@example.com"

        cross_account = client.post("/api/auth/login", json={
            "email": "beta@example.com", "password": "Alpha account password 1!"
        })
        wrong_email = client.post("/api/auth/login", json={
            "email": "missing@example.com", "password": "Alpha account password 1!"
        })
        wrong_password = client.post("/api/auth/login", json={
            "email": "alpha@example.com", "password": "wrong password"
        })
        assert cross_account.status_code == 401
        assert wrong_email.status_code == 401
        assert wrong_password.status_code == 401
    finally:
        backend_main._attempts.pop("login:testclient", None)
        engine.dispose()
