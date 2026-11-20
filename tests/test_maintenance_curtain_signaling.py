import asyncio
import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.main import Hub, audit_session, valid_curtain_disable, valid_curtain_request
from backend.database import Base, AuditEvent


class FakeSocket:
    def __init__(self):
        self.text_messages = []
        self.binary_messages = []

    async def send_text(self, message):
        self.text_messages.append(message)

    async def send_bytes(self, message):
        self.binary_messages.append(message)


def test_curtain_signaling_is_limited_to_approved_matching_sessions():
    state = {"session_id": "session-A", "curtain_status": "inactive"}
    event = {"type": "curtain.request", "session_id": "session-A", "monitor_indexes": [1, 2]}
    assert valid_curtain_request(event, "admin", True, state, "session-A")
    assert not valid_curtain_request(event, "read_only", True, state, "session-A")
    assert not valid_curtain_request(event, "admin", False, state, "session-A")
    assert not valid_curtain_request(event, "admin", True, state, "session-B")
    assert not valid_curtain_request({**event, "monitor_indexes": [0]}, "admin", True, state, "session-A")
    assert not valid_curtain_request({**event, "monitor_indexes": [True]}, "admin", True, state, "session-A")
    assert valid_curtain_disable({"session_id": "session-A"}, state, "session-A")
    assert not valid_curtain_disable({"session_id": "session-B"}, state, "session-A")


def test_hub_relays_text_and_binary_only_to_other_session_peers():
    hub = Hub()
    host, viewer, second_viewer = FakeSocket(), FakeSocket(), FakeSocket()
    hub.hosts["123456789"] = host
    hub.viewers["123456789"] = {viewer, second_viewer}

    asyncio.run(hub.relay("123456789", viewer, '{"type":"curtain.request"}'))
    assert host.text_messages == ['{"type":"curtain.request"}']
    assert len(second_viewer.text_messages) == 1
    assert viewer.text_messages == []

    asyncio.run(hub.relay("123456789", host, b"frame"))
    assert viewer.binary_messages == [b"frame"]
    assert second_viewer.binary_messages == [b"frame"]
    assert host.binary_messages == []


def test_curtain_audit_records_are_append_only_session_correlated_json():
    engine = create_engine("sqlite+pysqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        audit_session(db, "curtain.capture_verified", 7, "123456789", "session-A",
                      {"monitor": 2, "capture_backend": "mss-gdi"})
        audit_session(db, "curtain.closed", 7, "123456789", "session-A",
                      {"reason": "local_exit"})
        rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id)).all()
        assert [row.action for row in rows] == ["curtain.capture_verified", "curtain.closed"]
        assert all(json.loads(row.detail)["session_id"] == "session-A" for row in rows)
        assert "mss-gdi" in rows[0].detail
        assert "secret" not in rows[0].detail
    engine.dispose()
