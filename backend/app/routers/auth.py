"""Autenticación con código de un solo uso (OTP)."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..core.limiter import limiter
from ..core.security import (
    create_access_token, decrypt_email, email_alias, email_hash_of, encrypt_email,
    hash_otp, new_otp_code, verify_otp,
)
from ..models import CandidateProfile, Company, Otp, User
from ..routers.deps import current_user, client_ip
from ..services import mailer

router = APIRouter(prefix="/auth", tags=["auth"])


class OtpRequest(BaseModel):
    email: EmailStr
    role: str = "candidate"
    name: str = ""


class OtpVerify(BaseModel):
    email: EmailStr
    code: str


def _get_or_create(db: Session, email: str, role: str, name: str) -> User:
    h = email_hash_of(email)
    user = db.query(User).filter(User.email_hash == h).first()
    if user:
        if role == "business" and user.role == "candidate":
            user.role = "business"
            if not user.company:
                db.add(Company(user_id=user.id, name=name or email.split("@")[0]))
            db.commit()
        return user
    user = User(
        email=email_alias(0),
        email_hash=h,
        email_enc=encrypt_email(email),
        name=name or email.split("@")[0],
        role=role if role in ("candidate", "business") else "candidate",
    )
    db.add(user)
    db.flush()
    user.email = email_alias(user.id)
    if user.role == "business":
        db.add(Company(user_id=user.id, name=name or email.split("@")[0]))
    else:
        db.add(CandidateProfile(user_id=user.id))
    db.commit()
    return user


@router.post("/request-otp")
def request_otp(body: OtpRequest, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    ok, wait = limiter.otp_ip("otp:ip:" + ip, settings.otp_max_per_window * 4, settings.otp_request_window_minutes)
    if not ok:
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Intenta en %d s." % wait)
    ok, wait = limiter.otp_email("otp:email:" + body.email.lower(), settings.otp_max_per_email_window, settings.otp_request_window_minutes)
    if not ok:
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Intenta en %d s." % wait)

    user = _get_or_create(db, body.email, body.role, body.name)

    # invalida los códigos anteriores
    db.query(Otp).filter(Otp.user_id == user.id, Otp.used.is_(False)).update({"used": True})

    code = new_otp_code()
    db.add(Otp(
        user_id=user.id,
        code_hash=hash_otp(code),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.otp_expire_minutes),
    ))
    db.commit()

    channel = mailer.send_code(body.email, code)
    resp = {
        "ok": True,
        "email": body.email,
        "user_id": user.id,
        "channel": channel,
        "message": "Código enviado" if channel != "none" else "El servidor no pudo enviar el código",
    }
    if settings.otp_dev_code:
        resp["dev_code"] = code
    return resp


@router.post("/verify-otp")
def verify(body: OtpVerify, db: Session = Depends(get_db)):
    h = email_hash_of(body.email)
    user = db.query(User).filter(User.email_hash == h).first()
    if not user:
        raise HTTPException(status_code=400, detail="Solicita un código primero")

    otp = (
        db.query(Otp)
        .filter(Otp.user_id == user.id, Otp.used.is_(False))
        .order_by(Otp.id.desc())
        .first()
    )
    if not otp:
        raise HTTPException(status_code=400, detail="Solicita un código primero")
    if otp.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="El código venció. Solicita uno nuevo")

    # AU06: bloqueo en el intento número o después del máximo
    if otp.attempts >= settings.otp_max_attempts:
        raise HTTPException(status_code=429, detail="Demasiados intentos. Solicita un código nuevo")

    otp.attempts += 1
    db.commit()

    if not verify_otp(body.code, otp.code_hash):
        if otp.attempts > settings.otp_max_attempts:
            raise HTTPException(status_code=429, detail="Demasiados intentos. Solicita un código nuevo")
        raise HTTPException(status_code=400, detail="Código incorrecto")

    otp.used = True
    db.commit()

    return {
        "access_token": create_access_token(user.id, user.role),
        "user": {
            "id": user.id,
            "email": body.email,
            "name": user.name,
            "role": user.role,
        },
    }


@router.get("/me")
def me(user: User = Depends(current_user)):
    """Datos de la sesión. Nunca devuelve el email en claro si está cifrado."""
    return {
        "id": user.id,
        "email": decrypt_email(user.email_enc),
        "name": user.name,
        "role": user.role,
        "phone": user.phone,
    }
