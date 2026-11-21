from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import asyncio, json, secrets, time
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
from .database import SessionLocal, init_db, User, Device, AuditEvent, verify_database_connection, DATABASE_KIND
from .security import hash_secret, verify_secret, issue_token, read_token, new_device_id, new_dynamic_password

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
        "features":{"websocket_binary_relay":True,"webrtc_ice_config":True,"device_pairing":True,"rbac":["admin","technician","read_only"],"file_transfer":True,"clipboard_sync":True,"recording":False},
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
    if datetime.now(timezone.utc) > device.password_expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(401, "Dynamic password expired; ask the device owner to rotate it")
    if not verify_secret(device.password_hash, data.password):
        raise HTTPException(401, "Invalid dynamic password")
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

class Hub:
    def __init__(self):
        self.hosts: dict[str, WebSocket] = {}
        self.viewers: dict[str, set[WebSocket]] = {}
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
            except Exception:
                pass

    def is_approved(self, device_id: str) -> bool:
        return device_id in self.approved

hub = Hub()
MAX_CLIPBOARD_CHARS = 64 * 1024
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_FILE_CHUNK_BYTES = 192 * 1024

def validate_clipboard(event: dict) -> bool:
    value = event.get("text")
    return isinstance(value, str) and len(value) <= MAX_CLIPBOARD_CHARS

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
            await ws.send_json({"type":"viewer_joined"})
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
                break
            elif kind == "host_approved":
                hub.approved.add(device_id)
                audit(db, "session.host_approved", device.owner_id, device_id)
                await hub.relay(device_id, ws, raw)
            elif kind == "clipboard_update" and hub.is_approved(device_id):
                if validate_clipboard(event):
                    audit(db, "clipboard.relayed", device.owner_id, device_id, f"characters={len(event['text'])}")
                    await hub.relay(device_id, ws, raw)
            elif kind in ("file_accept", "file_reject", "file_chunk", "file_complete"):
                transfer = hub.transfers.get(str(event.get("transfer_id", "")))
                if not transfer or transfer.get("device_id") != device_id or not hub.is_approved(device_id):
                    continue
                if kind == "file_chunk":
                    try:
                        import base64
                        chunk = base64.b64decode(event.get("data", ""), validate=True)
                    except Exception:
                        continue
                    if len(chunk) > MAX_FILE_CHUNK_BYTES:
                        continue
                if kind in ("file_accept", "file_reject"):
                    transfer["accepted"] = kind == "file_accept"
                    if kind == "file_reject":
                        hub.transfers.pop(str(event["transfer_id"]), None)
                if kind == "file_complete":
                    hub.transfers.pop(str(event["transfer_id"]), None)
                    audit(db, "file.received", device.owner_id, device_id, f"name={transfer['name']}; bytes={transfer['size']}")
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
    db = SessionLocal()
    registered = False
    user_id = None
    try:
        auth = await asyncio.wait_for(ws.receive_json(), timeout=10)
        print("RDP_VIEWER_AUTH_RECEIVED", flush=True)
        payload = read_token(auth.get("session_token",""))
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
        reject_viewer = False
        async with hub.lock:
            active = hub.viewers.setdefault(device_id,set())
            if active or sum(len(group) for group in hub.viewers.values()) >= settings.max_concurrent_sessions:
                reject_viewer = True
            else:
                active.add(ws)
                registered = True
        if reject_viewer:
            print("RDP_VIEWER_REJECTING_CONCURRENT", flush=True)
            await ws.send_json({"type":"viewer_rejected","code":4429,"detail":"Another viewer is already connected"})
            await ws.close(code=4429, reason="One active viewer per device")
            return
        print("RDP_VIEWER_REGISTERED", flush=True)
        await ws.send_json({"type":"viewer_connected","device_online":device_id in hub.hosts})
        await hub.relay(device_id, ws, json.dumps({"type":"viewer_joined"}))
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
            if kind == "heartbeat":
                await ws.send_json({"type":"heartbeat_ack","at":datetime.now(timezone.utc).isoformat()})
            elif kind == "control":
                if user_role != "read_only":
                    await hub.relay(device_id, ws, raw)
            elif kind == "clipboard_update" and hub.is_approved(device_id):
                if validate_clipboard(event):
                    audit(db, "clipboard.relayed", user_id, device_id, f"characters={len(event['text'])}")
                    await hub.relay(device_id, ws, raw)
            elif kind == "file_offer" and hub.is_approved(device_id):
                try:
                    transfer_id = str(event.get("transfer_id", ""))
                    name = safe_file_name(event.get("name"))
                    size = int(event.get("size", 0))
                    if not transfer_id or len(transfer_id) > 64 or size < 1 or size > MAX_FILE_BYTES:
                        continue
                except (ValueError, TypeError):
                    continue
                hub.transfers[transfer_id] = {"device_id":device_id,"name":name,"size":size,"received":0,"accepted":False}
                event["name"] = name
                audit(db, "file.offered", user_id, device_id, f"name={name}; bytes={size}")
                await hub.relay(device_id, ws, json.dumps(event))
            elif kind == "file_chunk" and hub.is_approved(device_id):
                transfer = hub.transfers.get(str(event.get("transfer_id", "")))
                if not transfer or transfer.get("device_id") != device_id or not transfer.get("accepted"):
                    continue
                try:
                    import base64
                    chunk = base64.b64decode(event.get("data", ""), validate=True)
                except Exception:
                    continue
                if not chunk or len(chunk) > MAX_FILE_CHUNK_BYTES or transfer["received"] + len(chunk) > transfer["size"]:
                    continue
                transfer["received"] += len(chunk)
                await hub.relay(device_id, ws, raw)
            elif kind == "file_complete" and hub.is_approved(device_id):
                transfer = hub.transfers.get(str(event.get("transfer_id", "")))
                if transfer and transfer.get("device_id") == device_id and transfer.get("accepted") and transfer["received"] == transfer["size"]:
                    await hub.relay(device_id, ws, raw)
            elif kind == "file_cancel":
                transfer_id = str(event.get("transfer_id", ""))
                if hub.transfers.pop(transfer_id, None):
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
            hub.approved.discard(device_id)
            for transfer_id, transfer in list(hub.transfers.items()):
                if transfer.get("device_id") == device_id:
                    hub.transfers.pop(transfer_id, None)
            await hub.relay(device_id, ws, json.dumps({"type":"viewer_left"}))
            async with hub.lock:
                hub.viewers.get(device_id,set()).discard(ws)
        db.close()

@app.get("/")
def index():
    file = Path("frontend/dist/index.html")
    if file.exists():
        return FileResponse(file)
    return {"service":"Remote Desk Pro","docs":"/docs"}

frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
