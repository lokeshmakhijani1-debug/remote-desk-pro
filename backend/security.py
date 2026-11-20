from datetime import datetime, timedelta, timezone
import secrets
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from .config import settings

_hasher = PasswordHasher()

def hash_secret(value: str) -> str:
    return _hasher.hash(value)

def verify_secret(encoded: str, value: str) -> bool:
    try:
        return _hasher.verify(encoded, value)
    except Exception:
        return False

def issue_token(subject: str, role: str, ttl: int | None = None, claims: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "role": role, "iat": now, "exp": now + timedelta(seconds=ttl or settings.session_ttl_seconds)}
    if claims:
        payload.update({key: value for key, value in claims.items() if key not in {"sub", "role", "iat", "exp"}})
    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")

def read_token(token: str) -> dict:
    return jwt.decode(token, settings.app_secret_key, algorithms=["HS256"])

def new_device_id() -> str:
    return f"{secrets.randbelow(900_000_000) + 100_000_000}"

def new_dynamic_password() -> str:
    return f"{secrets.randbelow(900_000) + 100_000:06d}"
