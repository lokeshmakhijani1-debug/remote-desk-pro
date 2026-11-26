from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import asyncio, json, logging, secrets, time, math
from collections import defaultdict
from pathlib import Path
from typing import Any
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .config import settings
from .database import SessionLocal, init_db, User, Device, AuditEvent, CommunityWorkflow, verify_database_connection, DATABASE_KIND
from .security import hash_secret, verify_secret, issue_token, read_token, new_device_id, new_dynamic_password

logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.app_env == "production" and (
        len(settings.app_secret_key) < 32
        or settings.app_secret_key in (
            "development-only-change-me",
            "development-only-change-me-use-32-bytes-minimum",
            "replace-with-a-long-random-secret",
        )
    ):
        raise RuntimeError("APP_SECRET_KEY must be a unique random secret of at least 32 characters in production")
    init_db()
    yield

app = FastAPI(title="Remote Desk Pro API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def current_user(authorization: str | None, db: Session) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        payload = read_token(authorization.split(" ", 1)[1])
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(401, "Account unavailable")
    return user

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class PairIn(BaseModel):
    name: str = Field(default="This computer", min_length=1, max_length=120)

class ConnectIn(BaseModel):
    device_id: str = Field(pattern=r"^\d{9}$")
    password: str = Field(pattern=r"^\d{6}$")

class WorkflowPublishIn(BaseModel):
    workflow: dict[str, Any]


_attempts: dict[str, list[float]] = defaultdict(list)

def enforce_rate_limit(key: str, limit: int = 8):
    now = time.monotonic()
    recent = [stamp for stamp in _attempts[key] if now - stamp < 300]
    if len(recent) >= limit:
        raise HTTPException(429, "Too many attempts. Try again in five minutes.")
    recent.append(now)
    _attempts[key] = recent

def audit(db: Session, action: str, user_id: int | None = None, device_id: str | None = None, detail: str = ""):
    db.add(AuditEvent(user_id=user_id, device_id=device_id, action=action, detail=detail[:500]))
    db.commit()

@app.get("/health", include_in_schema=False)
@app.get("/api/health")
def health():
    try:
        database = verify_database_connection()
    except Exception:
        raise HTTPException(503, "Database connection unavailable")
    return {"status":"ok","service":"remote-desk-pro","version":"0.1.0","transport":["websocket","webrtc-signaling"],"database":database,"capacity_target":settings.max_concurrent_sessions}

@app.get("/api/manifest")
def manifest():
    return {
        "name":"Remote Desk Pro",
        "api_version":"0.1.0",
        "features":{"websocket_binary_relay":True,"webrtc_ice_config":True,"device_pairing":True,"rbac":["admin","technician","read_only"],"file_transfer":True,"clipboard_sync":True,"recording":True,"privacy_banner":True},
        "limits":{"max_concurrent_viewers":settings.max_concurrent_sessions,"one_viewer_per_device":True},
        "deployment":{"environment":settings.app_env,"database_dialect":DATABASE_KIND,"database_table_prefix":"rdp_","persistent_disk_required_for_sqlite":True}
    }

@app.post("/api/auth/register")
def register(data: RegisterIn, db: Session = Depends(db_session)):
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Email already registered")
    count = db.scalar(select(func.count()).select_from(User)) or 0
    role = "admin" if count == 0 else "technician"
    user = User(email=data.email.lower(), password_hash=hash_secret(data.password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    audit(db, "user.registered", user.id)
    return {"access_token":issue_token(str(user.id), user.role),"token_type":"bearer","user":{"id":user.id,"email":user.email,"role":user.role}}

@app.post("/api/auth/login")
def login(data: LoginIn, request: Request, db: Session = Depends(db_session)):
    enforce_rate_limit("login:" + (request.client.host if request.client else "unknown"))
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not user.active or not verify_secret(user.password_hash, data.password):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token":issue_token(str(user.id), user.role),"token_type":"bearer","user":{"id":user.id,"email":user.email,"role":user.role}}

@app.get("/api/me")
def me(authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    user = current_user(authorization, db)
    return {"id":user.id,"email":user.email,"role":user.role}

@app.post("/api/devices/pair")
def pair(data: PairIn, authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    user = current_user(authorization, db)
    if user.role not in ("admin","technician"):
        raise HTTPException(403, "Read-only users cannot pair devices")
    device_id = new_device_id()
    while db.scalar(select(Device).where(Device.device_id == device_id)):
        device_id = new_device_id()
    secret = secrets.token_urlsafe(32)
    password = new_dynamic_password()
    expires = datetime.now(timezone.utc) + timedelta(seconds=settings.device_password_ttl_seconds)
    device = Device(device_id=device_id, owner_id=user.id, name=data.name, secret_hash=hash_secret(secret), password_hash=hash_secret(password), password_expires_at=expires)
    db.add(device)
    db.commit()
    audit(db, "device.paired", user.id, device_id)
    return {"device_id":device_id,"agent_secret":secret,"dynamic_password":password,"password_expires_at":expires.isoformat(),"agent_warning":"Agent secret is displayed once. Store it securely."}

def _get_unattended_pin_hash(db: Session, device_id: str) -> str | None:
    row = db.scalar(select(AuditEvent).where(AuditEvent.device_id == device_id, AuditEvent.action == "device.unattended_pin_hash").order_by(AuditEvent.id.desc()))
    return row.detail if (row and row.detail) else None

def _set_unattended_pin_hash(db: Session, user_id: int | None, device_id: str, pin_hash: str) -> None:
    db.add(AuditEvent(user_id=user_id, device_id=device_id, action="device.unattended_pin_hash", detail=pin_hash))
    db.commit()

class UnattendedPinIn(BaseModel):
    pin: str = Field(default="", max_length=8)

class AgentUnattendedPinIn(BaseModel):
    agent_secret: str = Field(min_length=16, max_length=256)
    pin: str = Field(default="", max_length=8)

@app.post("/api/devices/{device_id}/unattended-pin")
def set_unattended_pin(device_id: str, data: UnattendedPinIn, authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    user = current_user(authorization, db)
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    if not device or (user.role != "admin" and device.owner_id != user.id):
        raise HTTPException(404, "Device not found")
    pin = data.pin.strip()
    if pin and (len(pin) < 4 or len(pin) > 8 or not pin.isdigit()):
        raise HTTPException(400, "Trusted PIN must be 4-8 digits")
    _set_unattended_pin_hash(db, user.id, device_id, hash_secret(pin) if pin else "")
    audit(db, "device.unattended_pin_updated", user.id, device_id)
    return {"device_id": device_id, "unattended_enabled": bool(pin)}

@app.post("/api/devices/{device_id}/agent-unattended-pin")
def agent_set_unattended_pin(device_id: str, data: AgentUnattendedPinIn, db: Session = Depends(db_session)):
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    if not device or not verify_secret(device.secret_hash, data.agent_secret):
        raise HTTPException(401, "Invalid device credentials")
    pin = data.pin.strip()
    if pin and (len(pin) < 4 or len(pin) > 8 or not pin.isdigit()):
        raise HTTPException(400, "Trusted PIN must be 4-8 digits")
    _set_unattended_pin_hash(db, device.owner_id, device_id, hash_secret(pin) if pin else "")
    audit(db, "device.unattended_pin_synced", device.owner_id, device_id)
    return {"device_id": device_id, "unattended_enabled": bool(pin)}

@app.post("/api/devices/{device_id}/rotate-password")
def rotate_password(device_id: str, authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    user = current_user(authorization, db)
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    if not device or (user.role != "admin" and device.owner_id != user.id):
        raise HTTPException(404, "Device not found")
    password = new_dynamic_password()
    expires = datetime.now(timezone.utc) + timedelta(seconds=settings.device_password_ttl_seconds)
    device.password_hash = hash_secret(password)
    device.password_expires_at = expires
    db.commit()
    audit(db, "device.password_rotated", user.id, device_id)
    return {"device_id":device_id,"dynamic_password":password,"password_expires_at":expires.isoformat()}

@app.get("/api/devices")
def devices(authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    user = current_user(authorization, db)
    query = select(Device)
    if user.role != "admin":
        query = query.where(Device.owner_id == user.id)
    rows = db.scalars(query.order_by(Device.created_at.desc())).all()
    return [{"device_id":d.device_id,"name":d.name,"online":d.online,"password_expires_at":d.password_expires_at.isoformat()} for d in rows]

@app.post("/api/devices/connect")
def connect(data: ConnectIn, request: Request, authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    enforce_rate_limit("connect:" + (request.client.host if request.client else "unknown"))
    user = current_user(authorization, db)
    device = db.scalar(select(Device).where(Device.device_id == data.device_id))
    if not device:
        raise HTTPException(404, "Device not found")
    saved_pin_hash = _get_unattended_pin_hash(db, device.device_id)
    pin_ok = bool(saved_pin_hash and verify_secret(saved_pin_hash, data.password))
    if not pin_ok:
        if datetime.now(timezone.utc) > device.password_expires_at.replace(tzinfo=timezone.utc):
            raise HTTPException(401, "Dynamic password expired; ask the device owner to rotate it")
        if not verify_secret(device.password_hash, data.password):
            raise HTTPException(401, "Invalid dynamic password or Trusted PIN")
    # Sliding idle expiry: a valid connection refreshes the password's 24-hour
    # inactivity window. Rotation or the host agent's next launch still replaces it.
    device.password_expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.device_password_ttl_seconds)
    db.commit()
    token = issue_token(f"viewer:{user.id}:{device.device_id}", user.role, settings.session_ttl_seconds)
    audit(db, "session.requested", user.id, device.device_id)
    ice_servers = [{"urls":settings.stun_url}]
    if settings.turn_url:
        ice_servers.append({"urls":settings.turn_url,"username":settings.turn_username,"credential":settings.turn_credential})
    return {"session_token":token,"device_id":device.device_id,"ice_servers":ice_servers}

@app.get("/api/admin/audit")
def audit_logs(authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    user = current_user(authorization, db)
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)).all()
    return [{"action":r.action,"user_id":r.user_id,"device_id":r.device_id,"detail":r.detail,"at":r.created_at.isoformat()} for r in rows]


def _public_workflow_payload(source: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(source, dict) or source.get("schema_version") != 1:
        raise HTTPException(422, "Unsupported workflow schema")
    if source.get("is_public") is not True:
        raise HTTPException(403, "Workflow must be explicitly marked public before publishing")
    privacy = source.get("privacy") if isinstance(source.get("privacy"), dict) else {}
    if privacy.get("local_only") is True:
        raise HTTPException(403, "Local-only workflows cannot be transmitted; explicitly opt in first")
    if privacy.get("typed_text_recorded") or privacy.get("clipboard_recorded"):
        raise HTTPException(422, "Workflows containing typed text or clipboard data cannot be published")
    steps = source.get("steps")
    if not isinstance(steps, list) or not steps or len(steps) > 10000:
        raise HTTPException(422, "Workflow must contain between 1 and 10000 steps")
    try:
        encoded = json.dumps(source, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        raise HTTPException(422, "Workflow must be valid JSON")
    if len(encoded.encode("utf-8")) > 2_000_000:
        raise HTTPException(413, "Workflow exceeds the 2 MB community limit")
    forbidden = {"typed_text", "clipboard", "password", "secret", "input_value"}
    def inspect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).casefold() in forbidden:
                    raise HTTPException(422, "Workflow contains a prohibited sensitive field")
                inspect(item)
        elif isinstance(value, list):
            for item in value: inspect(item)
    inspect(source)
    clean = json.loads(encoded)
    clean["name"] = " ".join(str(clean.get("name") or "Community workflow").split())[:120]
    tags = clean.get("tags", [])
    clean["tags"] = [str(tag).strip()[:32] for tag in tags[:12] if str(tag).strip()] if isinstance(tags, list) else []
    clean["notes"] = str(clean.get("notes") or "").strip()[:1000]
    clean["is_public"] = True
    clean["privacy"] = {"typed_text_recorded": False, "clipboard_recorded": False, "local_only": False}
    return clean


@app.post("/api/workflows/publish")
def publish_workflow(data: WorkflowPublishIn, authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    user = current_user(authorization, db)
    workflow = _public_workflow_payload(data.workflow)
    row = CommunityWorkflow(owner_id=user.id, name=workflow["name"], description=workflow["notes"],
                            tags=workflow["tags"], workflow=workflow, is_public=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, "workflow.published", user.id, detail=f"workflow_id={row.id}")
    return {"id": row.id, "name": row.name, "tags": row.tags, "is_public": True, "created_at": row.created_at.isoformat()}


@app.get("/api/workflows/community")
def community_workflows(authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    current_user(authorization, db)
    rows = db.scalars(select(CommunityWorkflow).where(CommunityWorkflow.is_public.is_(True))
                      .order_by(CommunityWorkflow.created_at.desc()).limit(100)).all()
    return [{"id": row.id, "name": row.name, "description": row.description, "tags": row.tags,
             "workflow": row.workflow, "created_at": row.created_at.isoformat()} for row in rows]


@app.post("/api/workflows/import/{workflow_id}")
def import_community_workflow(workflow_id: int, authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    current_user(authorization, db)
    row = db.scalar(select(CommunityWorkflow).where(CommunityWorkflow.id == workflow_id,
                                                     CommunityWorkflow.is_public.is_(True)))
    if not row:
        raise HTTPException(404, "Public community workflow not found")
    imported = json.loads(json.dumps(row.workflow))
    imported["is_public"] = False
    imported["privacy"] = {"typed_text_recorded": False, "clipboard_recorded": False, "local_only": True}
    imported["imported_from"] = {"community_workflow_id": row.id, "published_at": row.created_at.isoformat()}
    return {"workflow": imported}


class Hub:
    def __init__(self):
        self.hosts: dict[str, WebSocket] = {}
        self.viewers: dict[str, set[WebSocket]] = {}
        self.viewer_owners: dict[str, dict[WebSocket, int]] = {}
        self.approved: set[str] = set()
        self.transfers: dict[str, dict[str, Any]] = {}
        self.lock = asyncio.Lock()

    async def register_host(self, device_id: str, ws: WebSocket):
        async with self.lock:
            previous = self.hosts.get(device_id)
            self.hosts[device_id] = ws
            self.approved.discard(device_id)
            return previous

    async def remove_host(self, device_id: str, ws: WebSocket) -> bool:
        async with self.lock:
            if self.hosts.get(device_id) is not ws:
                return False
            self.hosts.pop(device_id, None)
            self.approved.discard(device_id)
            for transfer_id, transfer in list(self.transfers.items()):
                if transfer.get("device_id") == device_id:
                    self.transfers.pop(transfer_id, None)
            return True

    async def register_viewer(self, device_id: str, ws: WebSocket, max_sessions: int, user_id: int) -> tuple[bool, int, int, WebSocket | None]:
        async with self.lock:
            active = self.viewers.setdefault(device_id, set())
            owners = self.viewer_owners.setdefault(device_id, {})
            previous = next((socket for socket, owner in owners.items() if owner == user_id), None)
            if owners and previous is None:
                return False, len(active), sum(len(group) for group in self.viewer_owners.values()), None
            total = sum(len(group) for group in self.viewer_owners.values())
            if previous is None and total >= max_sessions:
                return False, len(active), total, None
            if previous is not None:
                active.discard(previous)
                owners.pop(previous, None)
            active.add(ws)
            owners[ws] = user_id
            return True, len(active), total if previous is not None else total + 1, previous

    async def remove_viewer(self, device_id: str, ws: WebSocket) -> bool:
        async with self.lock:
            active = self.viewers.get(device_id)
            owners = self.viewer_owners.get(device_id)
            if not active or ws not in active or not owners or ws not in owners:
                return False
            active.discard(ws)
            owners.pop(ws, None)
            if not active:
                self.viewers.pop(device_id, None)
                self.viewer_owners.pop(device_id, None)
            return True

    async def detach_viewer(self, device_id: str, ws: WebSocket) -> bool:
        async with self.lock:
            active = self.viewers.get(device_id)
            if not active or ws not in active:
                return False
            active.discard(ws)
            if not active:
                self.viewers.pop(device_id, None)
            return True

    async def terminate_viewer(self, device_id: str) -> None:
        async with self.lock:
            self.viewers.pop(device_id, None)
            self.viewer_owners.pop(device_id, None)
            self.approved.discard(device_id)

    async def relay(self, device_id: str, sender: WebSocket, message: Any):
        async with self.lock:
            targets = ([self.hosts[device_id]] if device_id in self.hosts and self.hosts[device_id] is not sender else [])
            targets += [v for v in self.viewers.get(device_id,set()) if v is not sender]
        for target in targets:
            try:
                if isinstance(message, bytes):
                    await target.send_bytes(message)
                else:
                    await target.send_text(message)
            except (WebSocketDisconnect, OSError, RuntimeError):
                logger.warning("relay delivery failed device=%s target=%s", device_id, type(target).__name__, exc_info=True)

    def is_approved(self, device_id: str) -> bool:
        return device_id in self.approved

hub = Hub()
MAX_CLIPBOARD_CHARS = 64 * 1024
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_FILE_CHUNK_BYTES = 192 * 1024

def validate_clipboard(event: dict) -> bool:
    value = event.get("text")
    return isinstance(value, str) and len(value) <= MAX_CLIPBOARD_CHARS


def validate_text_event(event: dict) -> bool:
    value = event.get("text", "")
    key = event.get("key")
    if key is not None:
        return key in {"Enter", "Backspace", "Tab", "Escape"} and value == ""
    return isinstance(value, str) and 0 < len(value) <= 2048 and all(
        ord(char) >= 32 or char in "\n\r\t" for char in value
    )


def validate_control(event: dict) -> bool:
    kind = event.get("event")
    if kind == "privacy_screen":
        return event.get("enabled") in (True, False) and event.get("mode") in ("black", "banner")
    if kind == "mouse_move":
        try:
            x, y = float(event.get("x")), float(event.get("y"))
            return math.isfinite(x) and math.isfinite(y) and 0 <= x <= 1 and 0 <= y <= 1
        except (TypeError, ValueError):
            return False
    if kind in ("mouse_down", "mouse_up"):
        return event.get("button") in (0, 1, 2)
    if kind in ("key_down", "key_up"):
        key = event.get("key")
        return isinstance(key, str) and 0 < len(key) <= 32
    if kind == "text_input":
        value = event.get("text")
        return isinstance(value, str) and 0 < len(value) <= 4096
    if kind == "mouse_scroll":
        try:
            dx, dy = float(event.get("deltaX", 0)), float(event.get("deltaY", 0))
            return math.isfinite(dx) and math.isfinite(dy) and abs(dx) <= 2400 and abs(dy) <= 2400
        except (TypeError, ValueError):
            return False
    if kind == "workflow_replay":
        return set(event.keys()).issubset({"type", "event"})
    return False

def validate_recording_control(event: dict) -> bool:
    """Accept only explicit local recording actions with bounded resource settings."""
    action = event.get("action")
    if action == "stop":
        return True
    if action != "start":
        return False
    settings_value = event.get("settings")
    if not isinstance(settings_value, dict) or settings_value.get("save_mode", "local") != "local":
        return False
    duration = settings_value.get("max_duration_seconds", 1800)
    retention = settings_value.get("retention_count", 5)
    storage = settings_value.get("max_storage_mb", 1024)
    return (
        type(duration) is int and 60 <= duration <= 14400
        and type(retention) is int and 1 <= retention <= 100
        and type(storage) is int and 100 <= storage <= 20480
    )


def safe_file_name(value: Any) -> str:
    name = str(value or "").replace("\\x00", "").replace("\\\\", "/").split("/")[-1]
    if not name or name in (".", "..") or len(name) > 180:
        raise ValueError("Invalid file name")
    return name

@app.websocket("/ws/host/{device_id}")
async def host_socket(ws: WebSocket, device_id: str):
    await ws.accept()
    db = SessionLocal()
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    explicit_disconnect = False
    try:
        auth = await asyncio.wait_for(ws.receive_json(), timeout=10)
        if not device or auth.get("type") != "auth" or not verify_secret(device.secret_hash, str(auth.get("secret",""))):
            await ws.close(code=4401)
            return
        previous_host = await hub.register_host(device_id, ws)
        if previous_host is not None and previous_host is not ws:
            try:
                await previous_host.close(code=1012, reason="Host agent reconnected")
            except Exception:
                pass
        device.online = True
        db.commit()
        await ws.send_json({"type":"connected","device_id":device_id})
        await hub.relay(device_id, ws, json.dumps({"type":"host_online"}))
        # A viewer may already be waiting while this host reconnects.
        if hub.viewers.get(device_id):
            owners = hub.viewer_owners.get(device_id, {})
            waiting_viewer_id = next(iter(owners.values()), "unknown")
            await ws.send_json({"type":"viewer_joined", "viewer_id": str(waiting_viewer_id)})
        while True:
            packet = await ws.receive()
            raw = packet.get("bytes") if packet.get("bytes") is not None else packet.get("text")
            if raw is None:
                continue
            if isinstance(raw, bytes):
                await hub.relay(device_id, ws, raw)
                continue
            try:
                event = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            kind = event.get("type")
            if kind == "host_disconnected":
                explicit_disconnect = True
                await hub.relay(device_id, ws, json.dumps({"type":"host_disconnected"}))
                await hub.terminate_viewer(device_id)
                break
            elif kind == "host_approved":
                hub.approved.add(device_id)
                audit(db, "session.host_approved", device.owner_id, device_id)
                await hub.relay(device_id, ws, raw)
            elif kind == "host_denied":
                hub.approved.discard(device_id)
                await hub.relay(device_id, ws, raw)
            elif kind in ("clipboard_ack", "privacy_screen_ack", "recording_status") and hub.is_approved(device_id):
                await hub.relay(device_id, ws, raw)
            elif kind == "recording_control" and hub.is_approved(device_id):
                if validate_recording_control(event):
                    audit(db, "recording." + str(event.get("action")) + "_requested", device.owner_id, device_id)
                    await hub.relay(device_id, ws, raw)
            elif kind == "clipboard_paste" and hub.is_approved(device_id):
                if validate_clipboard(event):
                    audit(db, "clipboard.pasted", device.owner_id, device_id, f"characters={len(event['text'])}")
                    await hub.relay(device_id, ws, raw)
            elif kind == "text" and hub.is_approved(device_id):
                if validate_text_event(event):
                    await hub.relay(device_id, ws, raw)
            elif kind == "telemetry" and hub.is_approved(device_id):
                try:
                    fps = float(event.get("fps", 0))
                    ping = event.get("ping_ms")
                    ping_ms = None if ping is None else float(ping)
                    upload = float(event.get("upload_kbps", 0))
                    download = float(event.get("download_kbps", 0))
                    if not (0 <= fps <= 120 and 0 <= upload <= 10000000 and 0 <= download <= 10000000):
                        continue
                    if ping_ms is not None and not (0 <= ping_ms <= 60000):
                        continue
                except (TypeError, ValueError):
                    continue
                payload = {"type":"telemetry","fps":fps,"ping_ms":ping_ms,"upload_kbps":upload,"download_kbps":download}
                await hub.relay(device_id, ws, json.dumps(payload))
            elif kind == "clipboard_update" and hub.is_approved(device_id):
                if validate_clipboard(event):
                    audit(db, "clipboard.relayed", device.owner_id, device_id, f"characters={len(event['text'])}")
                    await hub.relay(device_id, ws, raw)
            elif kind and kind.startswith("transfer_") and hub.is_approved(device_id):
                # File bytes are opaque relay payloads: no server-side disk or transfer state.
                transfer_id = str(event.get("transfer_id", ""))
                if not (16 <= len(transfer_id) <= 64) or any(c not in "0123456789abcdefABCDEF-" for c in transfer_id):
                    continue
                if kind == "transfer_chunk":
                    try:
                        import base64
                        chunk = base64.b64decode(event.get("data", ""), validate=True)
                    except Exception:
                        continue
                    if not 1 <= len(chunk) <= 1024 * 1024:
                        continue
                    if not isinstance(event.get("offset"), int) or event["offset"] < 0:
                        continue
                elif kind == "transfer_init":
                    try:
                        size = int(event.get("total_size", 0))
                        chunk_size = int(event.get("chunk_size", 0))
                    except (TypeError, ValueError):
                        continue
                    if not 0 < size <= MAX_FILE_BYTES or not 256 * 1024 <= chunk_size <= 1024 * 1024:
                        continue
                await hub.relay(device_id, ws, raw)
    except (WebSocketDisconnect, asyncio.TimeoutError, OSError):
        # Network resets (including Windows WinError 64 on the client) are normal
        # disconnects; the host agent reconnects with bounded backoff.
        pass
    except RuntimeError as exc:
        if "disconnect message has been received" not in str(exc):
            raise
    finally:
        # Removal and identity check are atomic under the Hub lock.
        was_current_host = await hub.remove_host(device_id, ws)
        # A replaced/stale socket must not mark the newer host connection offline.
        if device and was_current_host:
            if not explicit_disconnect:
                await hub.relay(device_id, ws, json.dumps({"type":"host_offline"}))
            device.online = False
            db.commit()
            db.add(AuditEvent(user_id=device.owner_id,device_id=device_id,action="host.disconnected"))
            db.commit()
        db.close()

@app.websocket("/ws/viewer/{device_id}")
async def viewer_socket(ws: WebSocket, device_id: str):
    await ws.accept()
    logger.info("viewer websocket opened device=%s", device_id)
    await ws.send_json({"type":"relay_ready"})
    db = SessionLocal()
    registered = False
    user_id = None
    try:
        auth = await asyncio.wait_for(ws.receive_json(), timeout=10)
        if not isinstance(auth, dict) or auth.get("type") != "auth":
            logger.warning("viewer auth rejected device=%s reason=invalid_handshake_frame", device_id)
            await ws.close(code=4401, reason="Invalid viewer authentication frame")
            return
        logger.info("viewer auth frame received device=%s", device_id)
        payload = read_token(str(auth.get("session_token", "")))
        subject = payload.get("sub","").split(":")
        if len(subject) != 3 or subject[0] != "viewer" or subject[2] != device_id:
            await ws.close(code=4401)
            return
        user_id = int(subject[1])
        device = db.scalar(select(Device).where(Device.device_id == device_id))
        if not device or not db.get(User, user_id) or not db.get(User, user_id).active:
            await ws.close(code=4404)
            return
        user_role = payload.get("role","read_only")
        registered, active_count, total_count, previous_viewer = await hub.register_viewer(device_id, ws, settings.max_concurrent_sessions, user_id)
        if not registered:
            logger.warning("viewer rejected device=%s active_count=%s total_count=%s", device_id, active_count, total_count)
            await ws.send_json({"type":"viewer_rejected","code":4429,"detail":"Another authenticated viewer owns this device session"})
            await ws.close(code=4429, reason="Device session belongs to another viewer")
            return
        if previous_viewer is not None:
            try:
                await previous_viewer.close(code=1012, reason="Viewer session resumed on a new connection")
            except (WebSocketDisconnect, OSError, RuntimeError):
                logger.debug("Previous viewer socket already closed device=%s", device_id)
            logger.info("viewer session reclaimed device=%s user_id=%s", device_id, user_id)
        logger.info("viewer registered device=%s active_count=%s total_count=%s", device_id, active_count, total_count)
        await ws.send_json({"type":"viewer_connected","device_online":device_id in hub.hosts})
        host_socket = hub.hosts.get(device_id)
        if host_socket is not None:
            try:
                await host_socket.send_json({"type": "viewer_joined", "viewer_id": str(user_id)})
                logger.info("viewer_joined delivered to host device=%s", device_id)
            except (WebSocketDisconnect, OSError, RuntimeError):
                logger.exception("viewer_joined delivery failed device=%s", device_id)
                await ws.send_json({"type": "host_offline"})
        else:
            logger.warning("viewer registered without a connected host device=%s", device_id)
        while True:
            packet = await ws.receive()
            raw = packet.get("bytes") if packet.get("bytes") is not None else packet.get("text")
            if raw is None:
                continue
            if isinstance(raw, bytes):
                # Viewer binary uploads are not accepted; screen frames flow host -> viewer.
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind == "viewer_end":
                hub.approved.discard(device_id)
                active_host = hub.hosts.get(device_id)
                if active_host is not None:
                    try:
                        await active_host.send_json({"type": "viewer_left"})
                    except (WebSocketDisconnect, OSError, RuntimeError):
                        logger.warning("viewer_left delivery failed device=%s", device_id, exc_info=True)
                await hub.remove_viewer(device_id, ws)
                registered = False
                await ws.send_json({"type": "session_ended"})
                break
            elif kind == "heartbeat":
                await ws.send_json({"type":"heartbeat_ack","at":datetime.now(timezone.utc).isoformat(),
                                    "device_online":device_id in hub.hosts})
            elif kind == "control":
                if user_role != "read_only" and hub.is_approved(device_id) and validate_control(event):
                    await hub.relay(device_id, ws, raw)
            elif kind == "recording_control" and user_role != "read_only":
                if not hub.is_approved(device_id):
                    await ws.send_json({"type":"input_pending","operation":"recording","detail":"Waiting for host approval"})
                elif validate_recording_control(event):
                    audit(db, "recording." + str(event.get("action")) + "_requested", user_id, device_id)
                    await hub.relay(device_id, ws, raw)
            elif kind == "clipboard_paste" and user_role != "read_only":
                if not hub.is_approved(device_id):
                    await ws.send_json({"type":"input_pending","operation":"clipboard","detail":"Waiting for host approval"})
                elif validate_clipboard(event):
                    audit(db, "clipboard.pasted", user_id, device_id, f"characters={len(event['text'])}")
                    await hub.relay(device_id, ws, raw)
            elif kind == "text" and user_role != "read_only":
                if not hub.is_approved(device_id):
                    await ws.send_json({"type":"input_pending","operation":"text","detail":"Waiting for host approval"})
                elif validate_text_event(event):
                    await hub.relay(device_id, ws, raw)
            elif kind == "clipboard_update" and hub.is_approved(device_id):
                if validate_clipboard(event):
                    audit(db, "clipboard.relayed", user_id, device_id, f"characters={len(event['text'])}")
                    await hub.relay(device_id, ws, raw)
            elif kind and kind.startswith("transfer_") and hub.is_approved(device_id):
                transfer_id = str(event.get("transfer_id", ""))
                if not (16 <= len(transfer_id) <= 64) or any(c not in "0123456789abcdefABCDEF-" for c in transfer_id):
                    continue
                if kind == "transfer_chunk":
                    try:
                        import base64
                        chunk = base64.b64decode(event.get("data", ""), validate=True)
                    except Exception:
                        continue
                    if not 1 <= len(chunk) <= 1024 * 1024 or not isinstance(event.get("offset"), int) or event["offset"] < 0:
                        continue
                elif kind == "transfer_init":
                    try:
                        size = int(event.get("total_size", 0))
                        chunk_size = int(event.get("chunk_size", 0))
                    except (TypeError, ValueError):
                        continue
                    if not 0 < size <= MAX_FILE_BYTES or not 256 * 1024 <= chunk_size <= 1024 * 1024:
                        continue
                    event["name"] = safe_file_name(event.get("name"))
                    raw = json.dumps(event)
                await hub.relay(device_id, ws, raw)
    except (WebSocketDisconnect, OSError):
        pass
    except RuntimeError as exc:
        if "disconnect message has been received" not in str(exc):
            raise
    except asyncio.TimeoutError:
        await ws.close(code=4408)
    except Exception:
        await ws.close(code=4401)
    finally:
        if registered:
            # Keep the owner reservation for same-user reconnect, but terminate the
            # approved control session so host overlays/recorders are always cleaned up.
            detached = await hub.detach_viewer(device_id, ws)
            if detached:
                hub.approved.discard(device_id)
                active_host = hub.hosts.get(device_id)
                if active_host is not None:
                    try:
                        await active_host.send_json({"type": "viewer_left"})
                    except (WebSocketDisconnect, OSError, RuntimeError):
                        logger.warning("viewer disconnect cleanup delivery failed device=%s", device_id, exc_info=True)
                logger.info("viewer disconnected; approved session cleanup sent device=%s user_id=%s", device_id, user_id)
        db.close()

@app.get("/")
def index():
    file = Path("frontend/dist/index.html")
    if file.exists():
        return FileResponse(file)
    return {"service":"Remote Desk Pro","docs":"/docs"}

@app.get("/api/download/agent", include_in_schema=False)
@app.get("/download/agent", include_in_schema=False)
def download_agent():
    agent_path = Path(__file__).parent / "downloads" / "RemoteDeskPro-Agent.exe"
    if not agent_path.is_file():
        raise HTTPException(503, "Windows agent download is not available on this deployment")
    return FileResponse(
        agent_path,
        media_type="application/vnd.microsoft.portable-executable",
        filename="RemoteDeskPro-Agent.exe",
        headers={"Cache-Control": "public, max-age=300"},
    )

frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
