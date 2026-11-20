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
from .database import SessionLocal, init_db, User, Device, AuditEvent
from .security import hash_secret, verify_secret, issue_token, read_token, new_device_id, new_dynamic_password

@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.app_env == "production" and settings.app_secret_key in ("development-only-change-me", "replace-with-a-long-random-secret"):
        raise RuntimeError("APP_SECRET_KEY must be a unique secret in production")
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
    return {"status":"ok","service":"remote-desk-pro","version":"0.1.0","transport":["websocket","webrtc-signaling"],"database":"configured","capacity_target":settings.max_concurrent_sessions}

@app.get("/api/manifest")
def manifest():
    return {
        "name":"Remote Desk Pro",
        "api_version":"0.1.0",
        "features":{"websocket_binary_relay":True,"webrtc_ice_config":True,"device_pairing":True,"rbac":["admin","technician","read_only"],"file_transfer":False,"clipboard_sync":False,"recording":False},
        "limits":{"max_concurrent_viewers":settings.max_concurrent_sessions,"one_viewer_per_device":True},
        "deployment":{"environment":settings.app_env,"persistent_disk_required_for_sqlite":True}
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
    token = issue_token(f"viewer:{user.id}:{device.device_id}", user.role, 900)
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
        self.lock = asyncio.Lock()

    async def register_host(self, device_id: str, ws: WebSocket):
        async with self.lock:
            self.hosts[device_id] = ws

    async def remove_host(self, device_id: str, ws: WebSocket):
        async with self.lock:
            if self.hosts.get(device_id) is ws:
                self.hosts.pop(device_id, None)

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

hub = Hub()

@app.websocket("/ws/host/{device_id}")
async def host_socket(ws: WebSocket, device_id: str):
    await ws.accept()
    db = SessionLocal()
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    try:
        auth = await asyncio.wait_for(ws.receive_json(), timeout=10)
        if not device or auth.get("type") != "auth" or not verify_secret(device.secret_hash, str(auth.get("secret",""))):
            await ws.close(code=4401)
            return
        await hub.register_host(device_id, ws)
        device.online = True
        db.commit()
        await ws.send_json({"type":"connected","device_id":device_id})
        while True:
            packet = await ws.receive()
            data = packet.get("bytes") if packet.get("bytes") is not None else packet.get("text")
            if data is not None:
                await hub.relay(device_id, ws, data)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        await hub.remove_host(device_id, ws)
        if device:
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
    try:
        auth = await asyncio.wait_for(ws.receive_json(), timeout=10)
        payload = read_token(auth.get("session_token",""))
        subject = payload.get("sub","").split(":")
        if len(subject) != 3 or subject[0] != "viewer" or subject[2] != device_id:
            await ws.close(code=4401)
            return
        user_role = payload.get("role","read_only")
        device = db.scalar(select(Device).where(Device.device_id == device_id))
        if not device:
            await ws.close(code=4404)
            return
        async with hub.lock:
            active = hub.viewers.setdefault(device_id,set())
            if active or sum(len(group) for group in hub.viewers.values()) >= settings.max_concurrent_sessions:
                await ws.close(code=4429)
                return
            active.add(ws)
            registered = True
        await ws.send_json({"type":"viewer_connected","device_online":device_id in hub.hosts})
        await hub.relay(device_id, ws, json.dumps({"type":"viewer_joined"}))
        while True:
            packet = await ws.receive()
            data = packet.get("bytes") if packet.get("bytes") is not None else packet.get("text")
            if data is not None:
                if isinstance(data, str):
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "control" and user_role == "read_only":
                        continue
                await hub.relay(device_id, ws, data)
    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        await ws.close(code=4408)
    except Exception:
        await ws.close(code=4401)
    finally:
        if registered:
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
