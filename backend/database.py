from datetime import datetime, timezone
from sqlalchemy import create_engine, String, DateTime, Boolean, ForeignKey, Integer, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings

def normalize_database_url(url: str) -> str:
    """Use the installed Psycopg 3 driver for PostgreSQL URLs."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url

DATABASE_URL = normalize_database_url(settings.database_url)
DATABASE_KIND = "postgresql" if DATABASE_URL.startswith("postgresql+") else "sqlite" if DATABASE_URL.startswith("sqlite") else "other"
connect_args = {"check_same_thread": False} if DATABASE_KIND == "sqlite" else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
if DATABASE_KIND == "sqlite":
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def enable_sqlite_wal(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# Prefix every table to guarantee isolation inside shared Supabase databases.
class User(Base):
    __tablename__ = "rdp_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="technician")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class Device(Base):
    __tablename__ = "rdp_devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(9), unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("rdp_users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="This computer")
    secret_hash: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    password_expires_at: Mapped[datetime] = mapped_column(DateTime)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class AuditEvent(Base):
    __tablename__ = "rdp_audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(9), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

def verify_database_connection() -> str:
    """Return the active dialect only after a successful database round-trip."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return DATABASE_KIND

def init_db():
    # create_all is scoped to the three rdp_* models above; unrelated tables are never altered.
    verify_database_connection()
    Base.metadata.create_all(bind=engine)
