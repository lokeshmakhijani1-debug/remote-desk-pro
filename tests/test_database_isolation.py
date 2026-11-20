from backend.database import Base, normalize_database_url
from backend.database import User, Device, AuditEvent

def test_postgres_urls_use_psycopg3():
    assert normalize_database_url("postgres://u:p@host/db").startswith("postgresql+psycopg://")
    assert normalize_database_url("postgresql://u:p@host/db").startswith("postgresql+psycopg://")
    assert normalize_database_url("postgresql+psycopg://u:p@host/db").startswith("postgresql+psycopg://")

def test_application_tables_are_isolated():
    assert {User.__tablename__, Device.__tablename__, AuditEvent.__tablename__} == {
        "rdp_users", "rdp_devices", "rdp_audit_events"
    }
    assert Device.__table__.c.owner_id.foreign_keys.pop().target_fullname == "rdp_users.id"
