"""Deterministic scale and security regression tests for the relay control plane.

These tests exercise the in-process Hub and protocol validators without opening
production sockets, touching real recordings, or contacting live devices.
"""
import asyncio
import pytest
from fastapi import HTTPException

from backend.main import (
    Hub,
    enforce_rate_limit,
    validate_clipboard,
    validate_control,
    validate_recording_library_control,
)


class FakeSocket:
    async def send_text(self, _message):
        return None

    async def send_bytes(self, _message):
        return None

    async def close(self, **_kwargs):
        return None


def test_hub_admits_50_concurrent_viewers_and_rejects_51st():
    async def scenario():
        hub = Hub()
        sockets = [FakeSocket() for _ in range(51)]
        outcomes = await asyncio.gather(*[
            hub.register_viewer(f"device-{index:02d}", socket, 50, index + 1)
            for index, socket in enumerate(sockets)
        ])
        assert sum(1 for result in outcomes if result[0]) == 50
        assert sum(1 for result in outcomes if not result[0]) == 1
        assert sum(len(group) for group in hub.viewers.values()) == 50
        assert sum(len(group) for group in hub.viewer_owners.values()) == 50
    asyncio.run(scenario())


def test_hub_prevents_cross_user_takeover_but_allows_same_user_reconnect():
    async def scenario():
        hub = Hub()
        first, attacker, resumed = FakeSocket(), FakeSocket(), FakeSocket()
        accepted = await hub.register_viewer("device-123", first, 50, 7)
        denied = await hub.register_viewer("device-123", attacker, 50, 8)
        restored = await hub.register_viewer("device-123", resumed, 50, 7)
        assert accepted[0] is True
        assert denied[0] is False
        assert restored[0] is True and restored[3] is first
        assert hub.viewer_owners["device-123"] == {resumed: 7}
    asyncio.run(scenario())


def test_host_replacement_cleanup_is_identity_safe_and_clears_transfers():
    async def scenario():
        hub = Hub()
        old, current = FakeSocket(), FakeSocket()
        await hub.register_host("123456789", old)
        await hub.register_host("123456789", current)
        hub.transfers["transfer-1234567890"] = {"device_id": "123456789"}
        assert await hub.remove_host("123456789", old) is False
        assert hub.hosts["123456789"] is current
        assert await hub.remove_host("123456789", current) is True
        assert "transfer-1234567890" not in hub.transfers
    asyncio.run(scenario())


def test_rate_limiter_rejects_ninth_attempt_in_window():
    key = "production-scale-test:isolated"
    from backend import main
    main._attempts.pop(key, None)
    for _ in range(8):
        enforce_rate_limit(key)
    with pytest.raises(HTTPException) as error:
        enforce_rate_limit(key)
    assert error.value.status_code == 429
    main._attempts.pop(key, None)


def test_clipboard_and_recording_protocol_payloads_are_bounded():
    assert validate_clipboard({"text": "नमस्ते — Remote Desk Pro"})
    assert validate_clipboard({"text": "x" * (64 * 1024)})
    assert not validate_clipboard({"text": "x" * (64 * 1024 + 1)})
    assert validate_recording_library_control({"type": "recording_list"})
    assert not validate_recording_library_control({
        "type": "recording_delete", "filename": "../outside.mp4"
    })
    assert not validate_recording_library_control({
        "type": "recording_download_chunk",
        "filename": "session_valid.mp4", "offset": 0, "length": 1024 * 1024
    })


@pytest.mark.parametrize("payload", [
    {"event": "mouse_move", "x": 999, "y": -1},
    {"event": "mouse_move", "x": float("nan"), "y": 0.5},
    {"event": "key_down", "key": "k".repeat(33)},
])
def test_invalid_control_payloads_are_rejected(payload):
    assert not validate_control(payload)
