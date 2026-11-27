import asyncio

from agent.host_agent import (
    HOST_HEARTBEAT_INTERVAL_SECONDS,
    HOST_WS_PING_INTERVAL_SECONDS,
    HOST_WS_PING_TIMEOUT_SECONDS,
)
from backend.main import HOST_HEARTBEAT_TIMEOUT_SECONDS, acknowledge_host_heartbeat


def test_host_heartbeat_has_three_intervals_of_server_grace():
    assert HOST_HEARTBEAT_INTERVAL_SECONDS == 15
    assert HOST_HEARTBEAT_TIMEOUT_SECONDS >= HOST_HEARTBEAT_INTERVAL_SECONDS * 3


def test_websocket_keepalive_tolerates_transient_network_jitter():
    assert HOST_WS_PING_INTERVAL_SECONDS == 20
    assert HOST_WS_PING_TIMEOUT_SECONDS >= HOST_WS_PING_INTERVAL_SECONDS


def test_host_heartbeat_is_acknowledged_by_signaling_server():
    class FakeWebSocket:
        def __init__(self):
            self.messages = []

        async def send_json(self, message):
            self.messages.append(message)

    ws = FakeWebSocket()
    asyncio.run(acknowledge_host_heartbeat(ws))
    assert len(ws.messages) == 1
    assert ws.messages[0]["type"] == "host_heartbeat_ack"
    assert isinstance(ws.messages[0]["at"], str)
