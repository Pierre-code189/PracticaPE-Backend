from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import decode_token
from .. import models

bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token requerido")
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no activo")
    return user


def require_role(*roles):
    def _check(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Rol no autorizado")
        return user
    return _check


def notify(db, user_id, type_, title, body, link=""):
    if user_id:
        db.add(models.Notification(user_id=user_id, type=type_, title=title, body=body, link=link))


def job_out(job, db, viewer_id=None, reveal_contact=False):
    company = job.company
    applied = False
    if viewer_id:
        applied = db.query(models.Application).filter_by(job_id=job.id, candidate_id=viewer_id).first() is not None
    saved = False
    if viewer_id:
        saved = db.query(models.SavedJob).filter_by(job_id=job.id, candidate_id=viewer_id).first() is not None
    contact = {}
    if reveal_contact and applied and company:
        contact = {"phone": company.phone, "email": company.email, "website": company.website,
                   "company": company.name}
    return {
        "id": job.id, "title": job.title, "description": job.description,
        "modality": job.modality, "district": job.district, "city": job.city,
        "lat": job.lat, "lng": job.lng, "salary": job.salary, "positions": job.positions,
        "status": job.status, "source": job.source, "source_url": job.source_url,
        "views": job.views, "created_at": str(job.created_at),
        "company": {"id": company.id, "name": company.name, "sector": company.sector,
                    "district": company.district, "logo_url": company.logo_url} if company else None,
        "applied": applied, "saved": saved, "contact": contact,
        "applications_count": len(job.applications),
    }

def get_optional_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    if not creds: return None
    payload = decode_token(creds.credentials)
    if not payload: return None
    user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
    return user if user and user.is_active else None
