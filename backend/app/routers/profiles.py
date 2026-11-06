from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.database import get_db
from .. import models
from .deps import get_current_user

router = APIRouter(tags=["profiles"])


class ProfileIn(BaseModel):
    headline: str = ""
    summary: str = ""
    city: str = "Piura"
    district: str = "Piura"
    phone: str = ""
    skills: str = ""
    avatar_url: str = ""
    cover_url: str = ""


class ItemIn(BaseModel):
    kind: str = "experience"
    title: str = ""
    org: str = ""
    start: str = ""
    end: str = ""
    description: str = ""
    location: str = ""


class PhotoIn(BaseModel):
    url: str = ""
    caption: str = ""
    kind: str = "gallery"


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
    email: str = ""
    website: str = ""
    logo_url: str = ""
    cover_url: str = ""
    is_public: bool = True


def _profile(db, user):
    p = user.candidate
    if not p:
        p = models.CandidateProfile(user_id=user.id)
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


def profile_out(p):
    return {"id": p.id, "headline": p.headline, "summary": p.summary, "city": p.city,
            "district": p.district, "phone": p.phone, "skills": p.skills,
            "avatar_url": p.avatar_url, "cover_url": p.cover_url,
            "items": [{"id": i.id, "kind": i.kind, "title": i.title, "org": i.org, "start": i.start,
                       "end": i.end, "description": i.description, "location": i.location} for i in p.items],
            "photos": [{"id": ph.id, "url": ph.url, "caption": ph.caption, "kind": ph.kind} for ph in p.photos]}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role, "phone": user.phone}


@router.get("/me/profile")
def get_profile(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role != "candidate":
        raise HTTPException(403, "Solo candidatos")
    return profile_out(_profile(db, user))


@router.put("/me/profile")
def update_profile(body: ProfileIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = _profile(db, user)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return profile_out(p)


@router.post("/me/profile/items")
def add_item(body: ItemIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = _profile(db, user)
    item = models.ProfileItem(profile_id=p.id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, **body.model_dump()}


@router.delete("/me/profile/items/{item_id}")
def del_item(item_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = _profile(db, user)
    item = db.get(models.ProfileItem, item_id)
    if not item or item.profile_id != p.id:
        raise HTTPException(404, "Item no encontrado")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/me/profile/photos")
def add_photo(body: PhotoIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = _profile(db, user)
    ph = models.Photo(profile_id=p.id, **body.model_dump())
    db.add(ph)
    db.commit()
    db.refresh(ph)
    return {"id": ph.id, **body.model_dump()}


@router.delete("/me/profile/photos/{photo_id}")
def del_photo(photo_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = _profile(db, user)
    ph = db.get(models.Photo, photo_id)
    if not ph or ph.profile_id != p.id:
        raise HTTPException(404, "Foto no encontrada")
    db.delete(ph)
    db.commit()
    return {"ok": True}


@router.get("/me/applications")
def my_applications(db: Session = Depends(get_db), user=Depends(get_current_user)):
    apps = db.query(models.Application).filter_by(candidate_id=user.id).order_by(models.Application.id.desc()).all()
    return [{"id": a.id, "job_id": a.job_id, "job_title": a.job.title if a.job else "",
             "status": a.status, "message": a.message, "created_at": str(a.created_at)} for a in apps]


@router.get("/me/cv")
def cv(db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = _profile(db, user)
    lines = [f"{user.name or 'Candidato'}", user.email, p.phone, p.city,
             p.headline, p.summary, f"Habilidades: {p.skills}", ""]
    for kind in ("experience", "education", "certification", "language", "project"):
        items = [i for i in p.items if i.kind == kind]
        if items:
            lines.append(kind.upper())
            for i in items:
                lines.append(f"- {i.title} @ {i.org} ({i.start}-{i.end}) {i.location}: {i.description}")
    return PlainTextResponse("\n".join(lines), media_type="text/plain")


@router.get("/me/notifications")
def notifications(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(models.Notification).filter_by(user_id=user.id).order_by(models.Notification.id.desc()).limit(50).all()
    return [{"id": n.id, "type": n.type, "title": n.title, "body": n.body, "link": n.link,
             "is_read": n.is_read, "created_at": str(n.created_at)} for n in rows]


@router.patch("/me/notifications/{nid}/read")
def read_notification(nid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    n = db.get(models.Notification, nid)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Notificación no encontrada")
    n.is_read = True
    db.commit()
    return {"ok": True}


@router.get("/business/profile")
def get_company(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role not in ("business", "admin"):
        raise HTTPException(403, "Solo negocios")
    c = user.company
    if not c:
        c = models.Company(user_id=user.id, name=user.name)
        db.add(c)
        db.commit()
        db.refresh(c)
    return company_out(c)


def company_out(c):
    return {"id": c.id, "name": c.name, "ruc": c.ruc, "sector": c.sector, "description": c.description,
            "address": c.address, "district": c.district, "city": c.city, "lat": c.lat, "lng": c.lng,
            "phone": c.phone, "email": c.email, "website": c.website, "logo_url": c.logo_url,
            "cover_url": c.cover_url, "is_public": c.is_public, "is_verified": c.is_verified}


@router.put("/business/profile")
def update_company(body: CompanyIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = user.company
    if not c:
        c = models.Company(user_id=user.id)
        db.add(c)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return company_out(c)


@router.get("/business/dashboard")
def business_dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user.company:
        return {"jobs": 0, "applications": 0, "views": 0}
    jobs = db.query(models.Job).filter_by(company_id=user.company.id).all()
    apps = db.query(models.Application).filter(models.Application.job_id.in_([j.id for j in jobs])).count() if jobs else 0
    return {"jobs": len(jobs), "published": sum(1 for j in jobs if j.status == "published"),
            "applications": apps, "views": sum(j.views for j in jobs)}


@router.get("/companies")
def public_companies(db: Session = Depends(get_db)):
    rows = db.query(models.Company).filter_by(is_public=True).all()
    return [company_out(c) for c in rows]


@router.get("/companies/{cid}")
def public_company(cid: int, db: Session = Depends(get_db)):
    c = db.get(models.Company, cid)
    if not c or not c.is_public:
        raise HTTPException(404, "Empresa no encontrada")
    jobs = db.query(models.Job).filter_by(company_id=cid, status="published").all()
    out = company_out(c)
    out["jobs"] = [{"id": j.id, "title": j.title, "modality": j.modality, "district": j.district,
                    "salary": j.salary} for j in jobs]
    return out


class IntakeIn(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    message: str = ""
    type: str = "contact"


@router.post("/intake")
def intake(body: IntakeIn, db: Session = Depends(get_db)):
    lead = models.Lead(**body.model_dump())
    db.add(lead)
    models.log_event(db, "lead", f"{body.type} {body.email}")
    db.commit()
    return {"ok": True, "id": lead.id}
