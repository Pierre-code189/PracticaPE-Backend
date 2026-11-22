"""Seguridad: JWT, hash de OTP, cifrado de email y alias no identificable."""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from .config import settings

# bcrypt: 72 bytes. Se usa SHA-256 + base64 (56 bytes) para no depender de passlib,
# que falla con entradas largas al inicializar el backend.
def _digest(secret: str) -> bytes:
    return base64.b64encode(sha256((secret or "").encode("utf-8")).digest())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_digest(plain), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_digest(plain), hashed.encode("ascii"))
    except Exception:
        return False


def hash_otp(code: str) -> str:
    return bcrypt.hashpw(_digest("otp:" + code), bcrypt.gensalt(rounds=10)).decode("ascii")


def verify_otp(code: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_digest("otp:" + code), hashed.encode("ascii"))
    except Exception:
        return False


def _fernet() -> Fernet:
    """Clave Fernet derivada del SECRET_KEY (sin material embebido)."""
    raw = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def email_hash_of(email: str) -> str:
    """HMAC del correo: clave de búsqueda sin revelar el valor."""
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        (email or "").strip().lower().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def encrypt_email(email: str) -> str:
    if not email:
        return ""
    return _fernet().encrypt((email or "").encode("utf-8")).decode("ascii")


def decrypt_email(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except Exception:
        return ""


def email_alias(user_id: int) -> str:
    return "u%d@oculto.local" % user_id


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    payload = {
        "sub": str(user_id),
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


def new_otp_code() -> str:
    """6 dígitos, sin sesgo (se rechaza 000000 para evitar códigos triviales)."""
    while True:
        n = int.from_bytes(os.urandom(4), "big") % 1_000_000
        code = "%06d" % n
        if code != "000000":
            return code
