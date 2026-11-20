from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, User, Device, AuditEvent
from backend.security import hash_secret, issue_token


def test_curtain_signaling_is_session_scoped_and_audited(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(main, "init_db", lambda: Base.metadata.create_all(engine))
    main.hub.hosts.clear()
    main.hub.viewers.clear()
    main.hub.approved.clear()
    main.hub.sessions.clear()
    main.hub.capabilities.clear()
    main.hub.transfers.clear()

    with factory() as db:
        user = User(email="curtain-test@example.invalid", password_hash=hash_secret("unused"),
                    role="admin", active=True)
        db.add(user)
        db.flush()
        device = Device(
            device_id="123456789", owner_id=user.id, name="Test workstation",
            secret_hash=hash_secret("agent-secret"), password_hash=hash_secret("123456"),
            password_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            online=False,
        )
        db.add(device)
        db.commit()
        user_id = user.id

    try:
        with TestClient(main.app) as client:
            user_token = issue_token(str(user_id), "admin")
            response = client.post(
                "/api/devices/connect",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"device_id": "123456789", "password": "123456"},
            )
            assert response.status_code == 200
            session = response.json()
            session_id = session["session_id"]

            with client.websocket_connect("/ws/host/123456789") as host:
                host.send_json({"type": "auth", "secret": "agent-secret"})
                assert host.receive_json()["type"] == "connected"
                host.send_json({"type": "agent_capabilities", "monitors": [
                    {"index": 1, "width": 1920, "height": 1080}
                ]})

                with client.websocket_connect("/ws/viewer/123456789") as viewer:
                    viewer.send_json({"session_token": session["session_token"]})
                    assert viewer.receive_json()["type"] == "viewer_connected"
                    capabilities = viewer.receive_json()
                    assert capabilities["type"] == "agent_capabilities"
                    assert capabilities["monitors"][0]["index"] == 1
                    joined = host.receive_json()
                    assert joined == {"type": "viewer_joined", "session_id": session_id}

                    host.send_json({"type": "host_approved", "session_id": session_id})
                    assert viewer.receive_json()["type"] == "host_approved"

                    viewer.send_json({
                        "type": "curtain.request",
                        "session_id": session_id,
                        "monitor_indexes": [1],
                    })
                    request = host.receive_json()
                    assert request["type"] == "curtain.request"
                    assert request["session_id"] == session_id

                    host.send_json({"type": "curtain.approved", "session_id": session_id,
                                    "monitor_indexes": [1]})
                    assert viewer.receive_json()["type"] == "curtain.approved"
                    for kind, data in (
                        ("curtain.affinity_enabled", {"monitor": 1, "affinity": 17}),
                        ("curtain.capture_verified", {"monitor": 1, "capture_backend": "mss-gdi"}),
                        ("curtain.shown", {"monitors": [1], "capture_backend": "mss-gdi"}),
                        ("curtain.status", {"status": "active_verified", "monitors": [1]}),
                    ):
                        host.send_json({"type": kind, "session_id": session_id, **data})
                        assert viewer.receive_json()["type"] == kind

                assert host.receive_json()["type"] == "viewer_left"

        with factory() as db:
            rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id)).all()
            actions = [row.action for row in rows]
            expected = {
                "session.consent_requested", "session.consent_granted",
                "curtain.consent_requested", "curtain.consent_granted",
                "curtain.affinity_enabled", "curtain.capture_verified",
                "curtain.shown", "curtain.closed", "session.ended",
            }
            assert expected.issubset(set(actions))
            correlated = [row for row in rows if row.action in expected]
            for row in correlated:
                detail = json.loads(row.detail)
                assert detail["session_id"] == session_id
                assert "agent-secret" not in row.detail
                assert "123456" not in row.detail
    finally:
        main.hub.hosts.clear()
        main.hub.viewers.clear()
        main.hub.approved.clear()
        main.hub.sessions.clear()
        main.hub.capabilities.clear()
        main.hub.transfers.clear()
        engine.dispose()
