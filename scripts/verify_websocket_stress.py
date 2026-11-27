"""Real TCP/WebSocket loopback stress and disconnect verification for Remote Desk Pro.

Runs the actual FastAPI host/viewer relay under Uvicorn on an ephemeral loopback
port and an isolated temporary SQLite database. It never connects to Render.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import socket
import tempfile
import threading
import time
import tracemalloc
from datetime import datetime, timedelta, timezone

import uvicorn
import websockets
from sqlalchemy import create_engine

# Direct script execution puts scripts/ first on sys.path, not the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy.orm import sessionmaker

from backend import main as app_module
from backend.database import Base, Device, User
from backend.security import hash_secret, issue_token


def open_fd_count() -> int | None:
    proc_fd = Path("/proc/self/fd")
    return len(list(proc_fd.iterdir())) if proc_fd.exists() else None


async def exercise_pair(base_url: str, device_id: str, secret: str, token: str, index: int) -> None:
    host_uri = base_url.replace("http://", "ws://") + f"/ws/host/{device_id}"
    viewer_uri = base_url.replace("http://", "ws://") + f"/ws/viewer/{device_id}"
    async with websockets.connect(host_uri, ping_interval=10, close_timeout=2, max_size=2**20) as host:
        await host.send(json.dumps({"type": "auth", "secret": secret}))
        connected = json.loads(await asyncio.wait_for(host.recv(), timeout=5))
        assert connected.get("type") == "connected"

        async with websockets.connect(viewer_uri, ping_interval=10, close_timeout=2, max_size=2**20) as viewer:
            ready = json.loads(await asyncio.wait_for(viewer.recv(), timeout=5))
            assert ready.get("type") == "relay_ready"
            await viewer.send(json.dumps({"type": "auth", "session_token": token}))
            accepted = json.loads(await asyncio.wait_for(viewer.recv(), timeout=5))
            assert accepted.get("type") == "viewer_connected"

            # Deterministic jitter creates varied scheduling without external network traffic.
            await asyncio.sleep((index % 5) * 0.015)
            await host.send(json.dumps({"type": "host_approved"}))
            approval = json.loads(await asyncio.wait_for(viewer.recv(), timeout=5))
            assert approval.get("type") == "host_approved"

            # Exercise the real approved viewer→host conversion request and validated
            # host→viewer JSON export relay as part of each concurrent stress pair.
            joined = json.loads(await asyncio.wait_for(host.recv(), timeout=5))
            assert joined.get("type") == "viewer_joined"
            recording_name = f"session_stress_{index}.mp4"
            await viewer.send(json.dumps({"type": "recording_convert_workflow", "filename": recording_name}))
            convert_request = json.loads(await asyncio.wait_for(host.recv(), timeout=5))
            assert convert_request == {"type": "recording_convert_workflow", "filename": recording_name}
            export_id = f"{index:024x}"
            export_data = json.dumps({"schema_version": 1, "steps": [{"action": "checkpoint"}]})
            await host.send(json.dumps({"type": "workflow_export_start", "export_id": export_id,
                                        "filename": "workflow_20261127T120000000000Z.json",
                                        "total_bytes": len(export_data.encode("utf-8"))}))
            start_frame = json.loads(await asyncio.wait_for(viewer.recv(), timeout=5))
            assert start_frame.get("type") == "workflow_export_start" and start_frame.get("export_id") == export_id
            await host.send(json.dumps({"type": "workflow_export_chunk", "export_id": export_id, "data": export_data}))
            chunk_frame = json.loads(await asyncio.wait_for(viewer.recv(), timeout=5))
            assert chunk_frame.get("type") == "workflow_export_chunk" and chunk_frame.get("data") == export_data
            await host.send(json.dumps({"type": "workflow_export_end", "export_id": export_id}))
            end_frame = json.loads(await asyncio.wait_for(viewer.recv(), timeout=5))
            assert end_frame == {"type": "workflow_export_end", "export_id": export_id}

            payload = bytes([index % 251]) * (16 * 1024)
            await host.send(payload)
            received = await asyncio.wait_for(viewer.recv(), timeout=5)
            assert isinstance(received, bytes) and received == payload

            if index % 3 == 0:
                # Abort the TCP transport to exercise abrupt viewer disconnect cleanup.
                viewer.transport.abort()
            else:
                await viewer.close(code=1000, reason="stress iteration complete")


async def run_clients(base_url: str, clients: int, rounds: int, secret: str, tokens: list[str], device_ids: list[str]) -> None:
    for round_index in range(rounds):
        offset = round_index * clients
        await asyncio.wait_for(
            asyncio.gather(*[
                exercise_pair(
                    base_url,
                    device_ids[offset + index],
                    secret,
                    tokens[offset + index],
                    offset + index,
                )
                for index in range(clients)
            ]),
            timeout=45,
        )
        await asyncio.sleep(0.15)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clients", type=int, default=12, help="Concurrent host/viewer pairs per round (1-48)")
    parser.add_argument("--rounds", type=int, default=2, help="Number of connect/disconnect rounds (1-5)")
    args = parser.parse_args()
    if not 1 <= args.clients <= 48 or not 1 <= args.rounds <= 5:
        parser.error("clients must be 1-48 and rounds must be 1-5")

    total = args.clients * args.rounds
    with tempfile.TemporaryDirectory(prefix="rdp-ws-stress-") as temporary:
        engine = create_engine(
            f"sqlite:///{Path(temporary) / 'stress.sqlite3'}",
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        secret = "loopback-only-agent-secret-not-for-production"
        secret_hash = hash_secret(secret)
        now = datetime.now(timezone.utc)
        device_ids = [f"{100000000 + index:09d}" for index in range(total)]
        tokens: list[str] = []
        with factory() as db:
            user = User(
                email="loopback-stress@example.com",
                password_hash="unused-loopback-test-hash",
                role="admin",
                active=True,
            )
            db.add(user)
            db.flush()
            for device_id in device_ids:
                db.add(Device(
                    device_id=device_id,
                    owner_id=user.id,
                    name="Isolated stress device",
                    secret_hash=secret_hash,
                    password_hash="unused-loopback-test-hash",
                    password_expires_at=now + timedelta(days=1),
                ))
                tokens.append(issue_token(f"viewer:{user.id}:{device_id}", "admin", 300))
            db.commit()

        app_module.SessionLocal = factory
        app_module.hub.hosts.clear()
        app_module.hub.viewers.clear()
        app_module.hub.viewer_owners.clear()
        app_module.hub.approved.clear()
        app_module.hub.transfers.clear()

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        config = uvicorn.Config(
            app_module.app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
            lifespan="off",
            ws_max_size=2**20,
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not server.started:
            server.should_exit = True
            thread.join(timeout=5)
            engine.dispose()
            raise RuntimeError("Uvicorn loopback server did not start")

        base_url = f"http://127.0.0.1:{port}"
        fd_before = open_fd_count()
        tracemalloc.start()
        memory_before, _ = tracemalloc.get_traced_memory()
        try:
            asyncio.run(run_clients(base_url, args.clients, args.rounds, secret, tokens, device_ids))
            time.sleep(0.35)
            memory_after, memory_peak = tracemalloc.get_traced_memory()
            fd_after = open_fd_count()
            assert not app_module.hub.hosts, f"Host sockets leaked: {len(app_module.hub.hosts)}"
            assert not app_module.hub.viewers, f"Viewer sockets leaked: {len(app_module.hub.viewers)}"
            assert memory_peak - memory_before < 128 * 1024 * 1024, "Loopback stress exceeded 128 MiB traced peak growth"
            if fd_before is not None and fd_after is not None:
                assert fd_after <= fd_before + 4, f"File descriptors leaked: before={fd_before}, after={fd_after}"
            print(json.dumps({
                "status": "passed",
                "transport": "real TCP loopback WebSocket via Uvicorn",
                "clients_per_round": args.clients,
                "rounds": args.rounds,
                "completed_pairs": total,
                "payload_bytes_per_pair": 16 * 1024,
                "jitter": "0-60ms deterministic",
                "abrupt_disconnects": (total + 2) // 3,
                "active_hosts_after": len(app_module.hub.hosts),
                "active_viewers_after": len(app_module.hub.viewers),
                "traced_memory_growth_bytes": max(0, memory_after - memory_before),
                "traced_peak_growth_bytes": max(0, memory_peak - memory_before),
                "file_descriptors_before": fd_before,
                "file_descriptors_after": fd_after,
            }, indent=2))
        finally:
            tracemalloc.stop()
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("Uvicorn loopback server did not stop cleanly")
            engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
