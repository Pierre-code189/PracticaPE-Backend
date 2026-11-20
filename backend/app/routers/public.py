"""Formularios públicos: contacto / intake de empresas."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.limiter import limiter
from ..models import Lead
from ..routers.deps import client_ip

router = APIRouter(tags=["public"])


class IntakeIn(BaseModel):
    name: str = ""
    email: EmailStr = ""
    phone: str = ""
    message: str = ""
    type: str = "contact"


@router.post("/intake")
def intake(body: IntakeIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    if not limiter.intake("intake:" + ip, 60):
        raise HTTPException(status_code=429, detail="Espera un momento antes de enviar otro mensaje")
    if not body.name.strip() or len(body.name.strip()) < 3:
        raise HTTPException(status_code=400, detail="Escribe tu nombre")
    if len(body.message.strip()) < 10:
        raise HTTPException(status_code=400, detail="Cuéntanos un poco más")
    lead = Lead(
        name=body.name.strip()[:255],
        email=str(body.email).strip()[:255],
        phone=body.phone.strip()[:50],
        message=body.message.strip()[:4000],
        type=body.type.strip()[:50] or "contact",
        status="new",
    )
    db.add(lead)
    db.commit()
    return {"ok": True, "lead_id": lead.id}
