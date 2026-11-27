import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, User, SavedWorkflow, CommunityWorkflow
from backend.security import hash_secret, issue_token


@pytest.fixture()
def workflow_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        owner = User(email="workflow-owner@example.test", password_hash=hash_secret("not-a-real-password"), role="admin")
        other = User(email="workflow-other@example.test", password_hash=hash_secret("not-a-real-password"), role="technician")
        db.add_all([owner, other]); db.commit(); db.refresh(owner); db.refresh(other)
        owner_token, other_token, owner_id = issue_token(str(owner.id), owner.role), issue_token(str(other.id), other.role), owner.id
    def override_db():
        with Session() as db:
            yield db
    main.app.dependency_overrides[main.db_session] = override_db
    try:
        with TestClient(main.app) as client:
            yield client, owner_token, other_token, Session, owner_id
    finally:
        main.app.dependency_overrides.pop(main.db_session, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def workflow():
    return {"schema_version": 1, "coordinate_space": "normalized_0_to_1", "name": "Recorded workflow",
            "tags": ["support"], "notes": "safe notes",
            "steps": [{"action": "mouse_down", "x": 0.5, "y": 0.5, "delay_ms": 0}],
            "privacy": {"typed_text_recorded": False, "clipboard_recorded": False, "local_only": True}}


def test_saved_workflow_owner_scope_and_lifecycle(workflow_client):
    client, owner, other, Session, owner_id = workflow_client
    created = client.post("/api/workflows", headers={"Authorization": "Bearer " + owner},
                          json={"workflow": workflow(), "source_recording": "session_example.mp4"})
    assert created.status_code == 200
    workflow_id = created.json()["id"]
    listed = client.get("/api/workflows", headers={"Authorization": "Bearer " + owner})
    assert listed.status_code == 200 and listed.json()[0]["id"] == workflow_id
    assert listed.json()[0]["is_public"] is False
    assert client.get("/api/workflows", headers={"Authorization": "Bearer " + other}).json() == []
    assert client.delete(f"/api/workflows/{workflow_id}", headers={"Authorization": "Bearer " + other}).status_code == 404
    published = client.post(f"/api/workflows/{workflow_id}/publish", headers={"Authorization": "Bearer " + owner}, json={})
    assert published.status_code == 200 and published.json()["is_public"] is True
    with Session() as db:
        assert db.scalar(select(CommunityWorkflow).where(CommunityWorkflow.owner_id == owner_id)) is not None
    unpublish = client.post(f"/api/workflows/{workflow_id}/unpublish", headers={"Authorization": "Bearer " + owner}, json={})
    assert unpublish.status_code == 200 and unpublish.json()["is_public"] is False
    with Session() as db:
        assert db.scalar(select(CommunityWorkflow).where(CommunityWorkflow.owner_id == owner_id)) is None
    assert client.delete(f"/api/workflows/{workflow_id}", headers={"Authorization": "Bearer " + owner}).json()["deleted"] is True


def test_saved_workflow_rejects_sensitive_payloads_and_requires_auth(workflow_client):
    client, owner, _, Session, _ = workflow_client
    assert client.get("/api/workflows").status_code == 401
    bad = workflow(); bad["steps"][0]["typed_text"] = "must-never-persist"
    assert client.post("/api/workflows", headers={"Authorization": "Bearer " + owner},
                       json={"workflow": bad}).status_code == 422
    with Session() as db:
        assert db.scalar(select(SavedWorkflow)) is None


def test_saved_workflow_rejects_unsupported_actions(workflow_client):
    client, owner, _, _, _ = workflow_client
    bad = workflow(); bad["steps"] = [{"action": "type_text", "text": "sensitive"}]
    assert client.post("/api/workflows", headers={"Authorization": "Bearer " + owner},
                       json={"workflow": bad}).status_code == 422


def test_saved_workflow_rejects_printable_keyboard_actions(workflow_client):
    client, owner, _, _, _ = workflow_client
    bad = workflow()
    bad["steps"] = [{"action": "key_down", "key": "a", "delay_ms": 0}]
    response = client.post("/api/workflows", headers={"Authorization": "Bearer " + owner},
                           json={"workflow": bad})
    assert response.status_code == 422
