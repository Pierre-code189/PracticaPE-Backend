import random
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..core.config import settings
from ..core.limiter import check as rate_check
from ..core.security import create_access_token, dec_email, email_hash, hash_password, verify_password
from ..core.database import get_db
from ..services import mailer

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
PUBLIC_ROLES = ("candidate", "business")


class RequestOtp(BaseModel):
    email: str
    name: str = ""
    role: str = "candidate"


class VerifyOtp(BaseModel):
    email: str
    code: str


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


@router.post("/request-otp")
def request_otp(body: RequestOtp, request: Request, db: Session = Depends(get_db)):
    email = (body.email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Email inválido")

    # Cuota por cuenta y por IP (CI: límite de solicitudes de OTP)
    ok, retry = rate_check(f"otp:email:{email}", settings.otp_max_per_window,
                           settings.otp_request_window_minutes * 60)
    if not ok:
        raise HTTPException(429, f"Demasiadas solicitudes. Intenta en {retry} s.")
    ok, retry = rate_check(f"otp:ip:{_client_ip(request)}", settings.otp_max_per_window * 4,
                           settings.otp_request_window_minutes * 60)
    if not ok:
        raise HTTPException(429, f"Demasiadas solicitudes. Intenta en {retry} s.")

    user = db.query(models.User).filter(models.User.email_hash == email_hash(email)).first()
    if not user:
        # El alta pública nunca puede crear administradores (PE01).
        role = body.role if body.role in PUBLIC_ROLES else "candidate"
        user = models.User(email=f"u0@oculto.local", email_hash=email_hash(email),
                           email_enc="", name=(body.name or "").strip()[:200], role=role)
        db.add(user)
        db.flush()
        user.email_enc = _enc(email)
        user.email = f"u{user.id}@oculto.local"
    elif body.name and not user.name:
        user.name = body.name.strip()[:200]

    # Si la cuenta tiene un OTP bloqueado y no vencido, no se puede reemitir (AU07).
    bloqueado = (db.query(models.Otp).filter_by(user_id=user.id, used=False)
                 .filter(models.Otp.attempts >= settings.otp_max_attempts).first())
    if bloqueado and bloqueado.expires_at > datetime.utcnow():
        db.commit()
        raise HTTPException(429, "Cuenta bloqueada por intentos. Solicita el código más tarde.")

    # Invalidate previous unused codes for this account.
    for old in db.query(models.Otp).filter_by(user_id=user.id, used=False).all():
        old.used = True

    code = f"{random.randint(0, 999999):06d}"
    db.add(models.Otp(user_id=user.id, code_hash=hash_password(code),
                      expires_at=datetime.utcnow() + timedelta(minutes=settings.otp_expire_minutes)))
    models.log_event(db, "otp_requested", email)
    db.commit()

    sent = mailer.send_otp(email, code, user.name)
    out = {"ok": True, "email": email, "user_id": user.id, "channel": "smtp" if sent else "none"}
    # El código solo se devuelve si el modo desarrollo está explícitamente activado (CI02).
    if settings.otp_dev_code:
        out["dev_code"] = code
    return out


def _enc(email: str) -> str:
    from ..core.security import enc_email
    return enc_email(email)


@router.post("/verify-otp")
def verify_otp(body: VerifyOtp, db: Session = Depends(get_db)):
    email = (body.email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Email inválido")
    user = db.query(models.User).filter(models.User.email_hash == email_hash(email)).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    otp = (db.query(models.Otp).filter_by(user_id=user.id, used=False)
           .order_by(models.Otp.id.desc()).first())
    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(400, "Código expirado o inexistente")
    # Bloqueo en el sexto intento (AU06): con 5 fallos ya registrados se rechaza.
    if otp.attempts >= settings.otp_max_attempts:
        raise HTTPException(400, "Demasiados intentos")
    if not verify_password((body.code or "").strip(), otp.code_hash):
        otp.attempts += 1
        db.commit()
        raise HTTPException(400, "Código incorrecto")
    otp.used = True
    models.log_event(db, "otp_verified", email)
    if user.role == "business" and not user.company:
        db.add(models.Company(user_id=user.id, name=user.name or "Mi empresa"))
    if user.role == "candidate" and not user.candidate:
        db.add(models.CandidateProfile(user_id=user.id))
    db.commit()
    token = create_access_token(user.id, user.role)
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": user.id, "email": dec_email(user.email_enc), "name": user.name,
                     "role": user.role}}
