"""Directorio público de empresas."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import Company, User
from ..routers.deps import optional_user

router = APIRouter(tags=["companies"])


def _company(c: Company) -> dict:
    jobs = [j for j in c.jobs if j.status == "published"]
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
        "published_jobs": len(jobs),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/companies")
def list_companies(
    q: str = "",
    sector: str = "",
    district: str = "",
    limit: int = 60,
    user: User = Depends(optional_user),
    db: Session = Depends(get_db),
):
    query = db.query(Company).filter(Company.is_public.is_(True))
    if q:
        like = "%" + q.strip().lower() + "%"
        query = query.filter((Company.name.ilike(like)) | (Company.description.ilike(like)))
    if sector:
        query = query.filter(Company.sector.ilike(sector))
    if district:
        query = query.filter(Company.district.ilike(district))
    items = query.order_by(Company.is_verified.desc(), Company.name.asc()).limit(limit).all()
    return {"items": [_company(c) for c in items], "total": len(items)}


@router.get("/companies/{company_id}")
def get_company(company_id: int, user: User = Depends(optional_user), db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c or not c.is_public:
        return {"detail": "Empresa no encontrada"}
    data = _company(c)
    data["jobs"] = [
        {
            "id": j.id, "title": j.title, "modality": j.modality, "district": j.district,
            "salary": j.salary, "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in c.jobs if j.status == "published"
    ]
    return data
