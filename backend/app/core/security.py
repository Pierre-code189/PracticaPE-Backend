import base64
import hashlib
import hmac
from datetime import datetime, timedelta

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from .config import settings


# ── Contraseñas / OTP ────────────────────────────────────────────────────────
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT ──────────────────────────────────────────────────────────────────────
def create_access_token(subject, role: str = "candidate") -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str):
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None


# ── Correo en reposo (CI03) ──────────────────────────────────────────────────
def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode("utf-8")).digest())
    return Fernet(key)


def enc_email(email: str) -> str:
    return _fernet().encrypt((email or "").strip().lower().encode("utf-8")).decode("ascii")


def dec_email(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except Exception:
        return ""


def email_hash(email: str) -> str:
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        (email or "").strip().lower().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def mask_email(email: str) -> str:
    """m@dominio.pe -> m***@dominio.pe (para listados administrativos)."""
    if not email or "@" not in email:
        return ""
    user, _, domain = email.partition("@")
    head = user[:2] if len(user) > 2 else user[:1]
    return f"{head}***@{domain}"
