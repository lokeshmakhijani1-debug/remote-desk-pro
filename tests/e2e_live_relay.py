"""Synthetic live relay verification for Remote Desk Pro.

Run: python tests/e2e_live_relay.py --base-url https://remote-desk-pro-pj29.onrender.com
Creates one synthetic account and one synthetic paired device in the configured database.
"""
import argparse
import asyncio
import base64
import json
import time
import uuid

import httpx
import websockets


def require(condition, message):
    if not condition:
        raise AssertionError(message)


async def receive_json(ws, expected_type, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        packet = await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.monotonic()))
        if isinstance(packet, bytes):
            continue
        event = json.loads(packet)
        if event.get("type") == expected_type:
            return event
    raise AssertionError(f"Timed out waiting for {expected_type}")


async def post_with_transport_retry(base_url, path, headers, payload, timeout):
    """Retry transient transport and Render gateway failures for this synthetic device."""
    last_error = None
    for attempt in range(5):
        try:
            limits = httpx.Limits(max_keepalive_connections=0)
            async with httpx.AsyncClient(base_url=base_url, timeout=timeout, limits=limits) as retry_client:
                response = await retry_client.post(path, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code not in {502, 503, 504} or attempt == 4:
                raise
        except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_error = exc
            if attempt == 4:
                raise
        await asyncio.sleep(min(2 ** attempt, 8))
    raise last_error


async def run(base_url):
    base_url = base_url.rstrip("/")
    ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
    timeout = httpx.Timeout(30.0)
    results = {}

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, limits=httpx.Limits(max_keepalive_connections=0)) as client:
        health = (await client.get("/api/health")).raise_for_status()
        health_data = health.json()
        require(health_data.get("database") == "postgresql", f"Expected PostgreSQL, got {health_data}")
        results["postgresql_health"] = "PASS"

        suffix = uuid.uuid4().hex[:12]
        email = f"rdp-e2e-{suffix}@example.com"
        password = f"Rdp-E2E-{uuid.uuid4().hex}!"
        reg = (await client.post("/api/auth/register", json={"email": email, "password": password})).raise_for_status().json()
        token = reg["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        results["synthetic_user_role"] = reg["user"]["role"]

        paired = (await client.post("/api/devices/pair", headers=headers, json={"name": f"E2E Synthetic {suffix}"})).raise_for_status().json()
        device_id = paired["device_id"]
        agent_secret = paired["agent_secret"]
        dynamic_password = paired["dynamic_password"]
        from datetime import datetime, timezone
        expires_at = datetime.fromisoformat(paired["password_expires_at"].replace("Z", "+00:00"))
        remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
        require(23 * 3600 <= remaining <= 24 * 3600 + 60, f"Expected 24-hour password window, got {remaining}s")
        results["device_registration"] = "PASS (same account owns host and viewer credentials)"
        results["dynamic_password_ttl"] = "PASS (24 hours)"

        connect = (await client.post(
            "/api/devices/connect", headers=headers,
            json={"device_id": device_id, "password": dynamic_password}
        )).raise_for_status().json()
        old_session_token = connect["session_token"]
        rotated = await post_with_transport_retry(base_url, f"/api/devices/{device_id}/rotate-password", headers, {}, timeout)
        rejected_old = None
        for attempt in range(5):
            rejected_old = await client.post("/api/devices/connect", headers=headers, json={"device_id": device_id, "password": dynamic_password})
            if rejected_old.status_code not in {502, 503, 504}:
                break
            await asyncio.sleep(min(2 ** attempt, 8))
        require(rejected_old.status_code == 401,
                f"Old dynamic password must be rejected after rotation; got HTTP {rejected_old.status_code}: {rejected_old.text[:180]}")
        dynamic_password = rotated["dynamic_password"]
        connect = (await client.post("/api/devices/connect", headers=headers, json={"device_id": device_id, "password": dynamic_password})).raise_for_status().json()
        session_token = old_session_token  # Existing viewer token survives password rotation.
        results["password_rotation_invalidation"] = "PASS (old password rejected; existing session token retained)"

        host_url = f"{ws_base}/ws/host/{device_id}"
        viewer_url = f"{ws_base}/ws/viewer/{device_id}"
        async with websockets.connect(host_url, max_size=8 * 1024 * 1024) as host:
            await host.send(json.dumps({"type": "auth", "secret": agent_secret}))
            await receive_json(host, "connected")
            devices = (await client.get("/api/devices", headers=headers)).raise_for_status().json()
            require(any(d["device_id"] == device_id and d["online"] for d in devices), "Host did not appear online")
            results["host_online_presence"] = "PASS"

            async with websockets.connect(viewer_url, max_size=8 * 1024 * 1024) as viewer:
                await receive_json(viewer, "relay_ready")
                await viewer.send(json.dumps({"type": "auth", "session_token": session_token}))
                await receive_json(viewer, "viewer_connected")
                await receive_json(host, "viewer_joined")

                frame = b"RDP-E2E-JPEG-FRAME-" + uuid.uuid4().bytes
                await host.send(frame)
                received_frame = await asyncio.wait_for(viewer.recv(), timeout=10)
                require(isinstance(received_frame, bytes) and received_frame == frame, "Binary frame relay mismatch")
                results["screen_frame_relay"] = f"PASS ({len(frame)} bytes)"

                await host.send(json.dumps({"type": "host_approved"}))
                await receive_json(viewer, "host_approved")

                host_clip = "host-to-viewer-" + suffix
                await host.send(json.dumps({"type": "clipboard_update", "text": host_clip}))
                got = await receive_json(viewer, "clipboard_update")
                require(got.get("text") == host_clip, "Host-to-viewer clipboard mismatch")

                viewer_clip = "viewer-to-host-" + suffix
                await viewer.send(json.dumps({"type": "clipboard_update", "text": viewer_clip}))
                got = await receive_json(host, "clipboard_update")
                require(got.get("text") == viewer_clip, "Viewer-to-host clipboard mismatch")
                results["bidirectional_clipboard"] = "PASS"

                # Four 48 KiB chunks exercise the multi-chunk transfer path.
                payload = (b"remote-desk-pro-e2e-file:" + suffix.encode()) * 5000
                transfer_id = uuid.uuid4().hex
                await viewer.send(json.dumps({
                    "type": "file_offer", "transfer_id": transfer_id,
                    "name": "../../rdp-e2e-synthetic.txt", "size": len(payload)
                }))
                offer = await receive_json(host, "file_offer")
                require(offer.get("name") == "rdp-e2e-synthetic.txt", "File name was not sanitized")
                await host.send(json.dumps({"type": "file_accept", "transfer_id": transfer_id}))
                await receive_json(viewer, "file_accept")

                chunk_size = 48 * 1024
                sent = 0
                chunks = 0
                while sent < len(payload):
                    chunk = payload[sent:sent + chunk_size]
                    await viewer.send(json.dumps({
                        "type": "file_chunk", "transfer_id": transfer_id,
                        "data": base64.b64encode(chunk).decode("ascii")
                    }))
                    packet = await asyncio.wait_for(host.recv(), timeout=10)
                    event = json.loads(packet)
                    require(event.get("type") == "file_chunk" and event.get("transfer_id") == transfer_id, "File chunk relay mismatch")
                    sent += len(chunk)
                    chunks += 1

                await viewer.send(json.dumps({"type": "file_complete", "transfer_id": transfer_id}))
                await receive_json(host, "file_complete")
                await host.send(json.dumps({"type": "file_complete", "transfer_id": transfer_id}))
                await receive_json(viewer, "file_complete")
                require(chunks > 1, "Transfer did not exercise multiple chunks")
                results["chunked_file_transfer"] = f"PASS ({sent} bytes, {chunks} chunks)"

                async with websockets.connect(viewer_url, max_size=8 * 1024 * 1024) as second_viewer:
                    await receive_json(second_viewer, "relay_ready")
                    await second_viewer.send(json.dumps({"type": "auth", "session_token": session_token}))
                    rejection = await receive_json(second_viewer, "viewer_rejected", timeout=15)
                    require(rejection.get("code") == 4429,
                            f"Expected explicit one-viewer rejection, got {rejection}")
                    # The browser client closes immediately after this explicit rejection event.
                    await second_viewer.close()
                await viewer.send(json.dumps({"type": "heartbeat"}))
                await receive_json(viewer, "heartbeat_ack")
                results["single_viewer_guard"] = "PASS (explicit rejection event; first viewer remains active)"

                await host.close(code=1011, reason="injected relay interruption")
                await receive_json(viewer, "host_offline")
                async with websockets.connect(host_url, max_size=8 * 1024 * 1024) as host2:
                    await host2.send(json.dumps({"type": "auth", "secret": agent_secret}))
                    await receive_json(host2, "connected")
                    await receive_json(viewer, "host_online")
                    await receive_json(host2, "viewer_joined")
                    await host2.send(json.dumps({"type": "host_approved"}))
                    await receive_json(viewer, "host_approved")
                    await viewer.send(json.dumps({"type": "heartbeat"}))
                    await receive_json(viewer, "heartbeat_ack")
                results["host_reconnect_with_live_viewer"] = "PASS (same viewer socket/token survived host reconnect)"

        if reg["user"]["role"] == "admin":
            audit_rows = (await client.get("/api/admin/audit", headers=headers)).raise_for_status().json()
            actions = {row["action"] for row in audit_rows if row.get("device_id") == device_id}
            expected = {"device.paired", "session.requested", "session.host_approved", "clipboard.relayed", "file.offered", "file.received"}
            missing = expected - actions
            require(not missing, f"Missing audit events: {sorted(missing)}")
            results["rdp_audit_persistence"] = "PASS (" + ", ".join(sorted(expected)) + ")"
        else:
            results["rdp_audit_persistence"] = "NOT_VERIFIED: synthetic account is not admin; audit endpoint is admin-only"

        print(json.dumps({"status": "PASS", "device_id": device_id, "email": email, "results": results}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://remote-desk-pro-pj29.onrender.com")
    args = parser.parse_args()
    asyncio.run(run(args.base_url))
