"""Panel de empresa: datos, KPIs, ofertas y postulantes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import Application, Company, Job, User
from ..routers.deps import current_user, require_role

router = APIRouter(tags=["business"])


def _comp(c: Company) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "ruc": c.ruc,
        "sector": c.sector,
        "description": c.description,
        "address": c.address,
        "district": c.district,
        "city": c.city,
        "lat": c.lat,
        "lng": c.lng,
        "phone": c.phone,
        "website": c.website,
        "logo_url": c.logo_url,
        "cover_url": c.cover_url,
        "is_public": c.is_public,
        "is_verified": c.is_verified,
    }


@router.get("/business/profile")
def business_profile(user: User = Depends(require_role("business", "admin")), db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.user_id == user.id).first()
    if not c:
        c = Company(user_id=user.id, name=user.name)
        db.add(c)
        db.commit()
        db.refresh(c)
    return _comp(c)


class CompanyIn(BaseModel):
    name: str = ""
    ruc: str = ""
    sector: str = ""
    description: str = ""
    address: str = ""
    district: str = "Piura"
    city: str = "Piura"
    lat: float = None
    lng: float = None
    phone: str = ""
    website: str = ""
    logo_url: str = ""
    cover_url: str = ""
    is_public: bool = True


@router.put("/business/profile")
def save_business_profile(body: CompanyIn, user: User = Depends(require_role("business", "admin")),
                         db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.user_id == user.id).first()
    if not c:
        c = Company(user_id=user.id)
        db.add(c)
    for f in ("name", "ruc", "sector", "description", "address", "district", "city",
              "lat", "lng", "phone", "website", "logo_url", "cover_url", "is_public"):
        if hasattr(body, f):
            setattr(c, f, getattr(body, f))
    if c.name:
        user.name = c.name
    db.commit()
    db.refresh(c)
    return _comp(c)


@router.get("/business/dashboard")
def dashboard(user: User = Depends(require_role("business", "admin")), db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.user_id == user.id).first()
    if not c:
        return {"published": 0, "draft": 0, "applications": 0, "candidates": 0, "views": 0}
    jobs = db.query(Job).filter(Job.company_id == c.id).all()
    published = [j for j in jobs if j.status == "published"]
    drafts = [j for j in jobs if j.status == "draft"]
    apps = db.query(Application).join(Job).filter(Job.company_id == c.id).count()
    cands = db.query(Application.candidate_id).join(Job).filter(Job.company_id == c.id).distinct().count()
    views = sum(j.views for j in jobs)
    return {
        "published": len(published),
        "draft": len(drafts),
        "closed": len([j for j in jobs if j.status == "closed"]),
        "applications": apps,
        "candidates": cands,
        "views": views,
    }


@router.get("/business/jobs")
def business_jobs(user: User = Depends(require_role("business", "admin")), db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.user_id == user.id).first()
    if not c:
        return {"items": []}
    items = db.query(Job).filter(Job.company_id == c.id).order_by(Job.id.desc()).all()
    return {"items": [
        {
            "id": j.id, "title": j.title, "status": j.status, "district": j.district,
            "modality": j.modality, "salary": j.salary, "positions": j.positions,
            "views": j.views,
            "applications": db.query(Application).filter(Application.job_id == j.id).count(),
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in items
    ]}
