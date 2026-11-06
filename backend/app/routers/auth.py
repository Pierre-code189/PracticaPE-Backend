import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.config import settings
from ..core.security import create_access_token, hash_password
from .. import models

router = APIRouter(prefix="/auth", tags=["auth"])


class RequestOtp(BaseModel):
    email: str
    name: str = ""
    role: str = "candidate"


class VerifyOtp(BaseModel):
    email: str
    code: str


@router.post("/request-otp")
def request_otp(body: RequestOtp, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Email inválido")
    user = db.query(models.User).filter_by(email=email).first()
    if not user:
        role = body.role if body.role in ("candidate", "business", "admin") else "candidate"
        user = models.User(email=email, name=body.name, role=role)
        db.add(user)
        db.flush()
    elif body.name and not user.name:
        user.name = body.name
    code = f"{random.randint(0, 999999):06d}"
    db.add(models.Otp(user_id=user.id, code_hash=hash_password(code),
                      expires_at=datetime.utcnow() + timedelta(minutes=settings.otp_expire_minutes)))
    models.log_event(db, "otp_requested", email)
    db.commit()
    out = {"ok": True, "email": email, "user_id": user.id}
    if settings.otp_dev_code:
        out["dev_code"] = code
    return out


@router.post("/verify-otp")
def verify_otp(body: VerifyOtp, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(models.User).filter_by(email=email).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    otp = (db.query(models.Otp).filter_by(user_id=user.id, used=False)
           .order_by(models.Otp.id.desc()).first())
    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(400, "Código expirado o inexistente")
    if otp.attempts > 5:
        raise HTTPException(400, "Demasiados intentos")
    from ..core.security import verify_password
    if not verify_password(body.code, otp.code_hash):
        otp.attempts += 1
        db.commit()
        raise HTTPException(400, "Código incorrecto")
    otp.used = True
    models.log_event(db, "otp_verified", email)
    # Auto-create profiles on first login
    if user.role == "business" and not user.company:
        db.add(models.Company(user_id=user.id, name=user.name or "Mi empresa"))
    if user.role == "candidate" and not user.candidate:
        db.add(models.CandidateProfile(user_id=user.id))
    db.commit()
    token = create_access_token(user.id, user.role)
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role}}
