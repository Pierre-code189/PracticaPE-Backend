import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..core.config import settings
from ..core.database import get_db
from ..core.security import dec_email
from .deps import get_current_user, require_role
from .jobs import job_out

router = APIRouter(tags=["profiles"])

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.getenv("PRACTICAPE_UPLOAD_DIR", os.path.join(_BASE, "data", "uploads"))


def _upload_dir(kind: str) -> str:
    d = os.path.join(UPLOAD_DIR, kind)
    os.makedirs(d, exist_ok=True)
    return d


def _save_upload(file: UploadFile, kind: str, user_id: int) -> str:
    ctype = (file.content_type or "").lower()
    if ctype not in settings.upload_allow:
        raise HTTPException(400, "Formato no permitido (JPEG, PNG o WebP)")
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(ctype, ".jpg")
    data = file.file.read(settings.upload_max_mb * 1024 * 1024 + 1)
    if len(data) > settings.upload_max_mb * 1024 * 1024:
        raise HTTPException(413, "Archivo demasiado grande")
    if not data:
        raise HTTPException(400, "Archivo vacío")
    name = f"u{user_id}_{secrets.token_hex(6)}{ext}"
    with open(os.path.join(_upload_dir(kind), name), "wb") as fh:
        fh.write(data)
    return f"/uploads/{kind}/{name}"


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


def company_out(c):
    return {"id": c.id, "name": c.name, "ruc": c.ruc, "sector": c.sector, "description": c.description,
            "address": c.address, "district": c.district, "city": c.city, "lat": c.lat, "lng": c.lng,
            "phone": c.phone, "email": c.email, "website": c.website, "logo_url": c.logo_url,
            "cover_url": c.cover_url, "is_public": c.is_public, "is_verified": c.is_verified}


# ── Sesión / perfil de candidato ─────────────────────────────────────────────
@router.get("/me")
def me(user=Depends(get_current_user)):
    return {"id": user.id, "email": dec_email(user.email_enc), "name": user.name,
            "role": user.role, "phone": user.phone}


@router.get("/me/profile")
def get_profile(db: Session = Depends(get_db), user=Depends(require_role("candidate"))):
    return profile_out(_profile(db, user))


@router.put("/me/profile")
def update_profile(body: ProfileIn, db: Session = Depends(get_db), user=Depends(require_role("candidate"))):
    p = _profile(db, user)
    data = body.model_dump()
    data["headline"] = (data.get("headline") or "").strip()[:200]
    data["summary"] = (data.get("summary") or "").strip()[:4000]
    data["skills"] = (data.get("skills") or "").strip()[:500]
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    return profile_out(p)


@router.post("/me/profile/items")
def add_item(body: ItemIn, db: Session = Depends(get_db), user=Depends(require_role("candidate"))):
    p = _profile(db, user)
    if not (body.title or "").strip():
        raise HTTPException(400, "El título es obligatorio")
    if body.kind not in ("experience", "education", "certification", "language", "project"):
        raise HTTPException(400, "Tipo de elemento inválido")
    item = models.ProfileItem(profile_id=p.id, kind=body.kind, title=body.title.strip()[:200],
                              org=body.org.strip()[:200], start=body.start.strip()[:20],
                              end=body.end.strip()[:20], description=body.description.strip()[:2000],
                              location=body.location.strip()[:100])
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "kind": item.kind, "title": item.title, "org": item.org, "start": item.start,
            "end": item.end, "description": item.description, "location": item.location}


@router.delete("/me/profile/items/{item_id}")
def del_item(item_id: int, db: Session = Depends(get_db), user=Depends(require_role("candidate"))):
    p = _profile(db, user)
    item = db.get(models.ProfileItem, item_id)
    if not item or item.profile_id != p.id:
        raise HTTPException(404, "Item no encontrado")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/me/profile/photos")
def add_photo(body: PhotoIn, db: Session = Depends(get_db), user=Depends(require_role("candidate"))):
    p = _profile(db, user)
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(400, "La URL es obligatoria")
    if not url.startswith(("http://", "https://", "/")):
        raise HTTPException(400, "URL no válida")
    ph = models.Photo(profile_id=p.id, url=url[:500], caption=body.caption.strip()[:200], kind=body.kind)
    db.add(ph)
    db.commit()
    db.refresh(ph)
    return {"id": ph.id, "url": ph.url, "caption": ph.caption, "kind": ph.kind}


@router.post("/me/profile/avatar")
async def upload_avatar(file: UploadFile, db: Session = Depends(get_db), user=Depends(require_role("candidate"))):
    p = _profile(db, user)
    p.avatar_url = _save_upload(file, "avatar", user.id)
    db.commit()
    return {"avatar_url": p.avatar_url}


@router.post("/me/profile/cover")
async def upload_cover(file: UploadFile, db: Session = Depends(get_db), user=Depends(require_role("candidate"))):
    p = _profile(db, user)
    p.cover_url = _save_upload(file, "cover", user.id)
    db.commit()
    return {"cover_url": p.cover_url}


@router.delete("/me/profile/photos/{photo_id}")
def del_photo(photo_id: int, db: Session = Depends(get_db), user=Depends(require_role("candidate"))):
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
             "job_status": a.job.status if a.job else "",
             "company": a.job.company.name if a.job and a.job.company else "",
             "status": a.status, "message": a.message, "created_at": str(a.created_at)} for a in apps]


@router.get("/me/cv")
def cv(db: Session = Depends(get_db), user=Depends(require_role("candidate"))):
    p = _profile(db, user)
    lines = [user.name or "Candidato", dec_email(user.email_enc), p.phone, f"{p.city} - {p.district}",
             "", p.headline, p.summary, "", f"Habilidades: {p.skills}", ""]
    for kind in ("experience", "education", "certification", "language", "project"):
        items = [i for i in p.items if i.kind == kind]
        if items:
            lines.append(kind.upper())
            for i in items:
                lines.append(f"- {i.title} @ {i.org} ({i.start}-{i.end}) {i.location}: {i.description}")
            lines.append("")
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


@router.post("/me/notifications/read-all")
def read_all_notifications(db: Session = Depends(get_db), user=Depends(get_current_user)):
    db.query(models.Notification).filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.commit()
    return {"ok": True}


@router.delete("/me")
def delete_account(db: Session = Depends(get_db), user=Depends(get_current_user)):
    user.is_active = False
    db.commit()
    return {"ok": True}


# ── Perfil público de candidato ──────────────────────────────────────────────
@router.get("/profile/{user_id}")
def public_profile(user_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    target = db.get(models.User, user_id)
    if not target or not target.is_active or target.role != "candidate":
        raise HTTPException(404, "Perfil no encontrado")
    p = target.candidate
    if not p:
        raise HTTPException(404, "Perfil no encontrado")
    can_see_contact = bool(user and user.id == target.id)
    return {
        "id": target.id, "name": target.name, "headline": p.headline, "summary": p.summary,
        "city": p.city, "district": p.district,
        "phone": p.phone if can_see_contact else "",
        "email": dec_email(target.email_enc) if can_see_contact else "",
        "skills": p.skills, "avatar_url": p.avatar_url, "cover_url": p.cover_url,
        "items": [{"id": i.id, "kind": i.kind, "title": i.title, "org": i.org, "start": i.start,
                   "end": i.end, "description": i.description, "location": i.location} for i in p.items],
    }


# ── Empresa ──────────────────────────────────────────────────────────────────
@router.get("/business/profile")
def get_company(db: Session = Depends(get_db), user=Depends(require_role("business", "admin"))):
    c = user.company
    if not c:
        if user.role == "admin":
            raise HTTPException(400, "El administrador no tiene empresa asignada")
        c = models.Company(user_id=user.id, name=user.name)
        db.add(c)
        db.commit()
        db.refresh(c)
    return company_out(c)


@router.put("/business/profile")
def update_company(body: CompanyIn, db: Session = Depends(get_db), user=Depends(require_role("business", "admin"))):
    c = user.company
    if not c:
        if user.role == "admin":
            raise HTTPException(400, "El administrador no tiene empresa asignada")
        c = models.Company(user_id=user.id)
        db.add(c)
        db.flush()
    data = body.model_dump()
    data["name"] = (data.get("name") or "").strip()[:200]
    if not data["name"]:
        raise HTTPException(400, "El nombre de la empresa es obligatorio")
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    return company_out(c)


@router.post("/business/logo")
async def upload_logo(file: UploadFile, db: Session = Depends(get_db), user=Depends(require_role("business", "admin"))):
    c = user.company or models.Company(user_id=user.id, name=user.name)
    if not c.id:
        db.add(c)
        db.flush()
    c.logo_url = _save_upload(file, "logo", user.id)
    db.commit()
    return {"logo_url": c.logo_url}


@router.get("/business/jobs")
def business_jobs(db: Session = Depends(get_db), user=Depends(require_role("business", "admin"))):
    """Todas las convocatorias de la empresa (borradores, publicadas y cerradas)."""
    if not user.company:
        return []
    rows = db.query(models.Job).filter_by(company_id=user.company.id).order_by(models.Job.id.desc()).limit(200).all()
    return [job_out(j, db, viewer_id=user.id) for j in rows]


@router.get("/business/dashboard")
def business_dashboard(db: Session = Depends(get_db), user=Depends(require_role("business", "admin"))):
    if not user.company:
        return {"jobs": 0, "published": 0, "applications": 0, "views": 0}
    jobs = db.query(models.Job).filter_by(company_id=user.company.id).all()
    apps = db.query(models.Application).filter(
        models.Application.job_id.in_([j.id for j in jobs])).count() if jobs else 0
    return {"jobs": len(jobs), "published": sum(1 for j in jobs if j.status == "published"),
            "applications": apps, "views": sum(j.views for j in jobs)}


@router.get("/companies")
def public_companies(db: Session = Depends(get_db)):
    rows = db.query(models.Company).filter_by(is_public=True).order_by(models.Company.id.desc()).limit(100).all()
    return [{"id": c.id, "name": c.name, "sector": c.sector, "district": c.district,
             "logo_url": c.logo_url, "is_verified": c.is_verified,
             "jobs": db.query(models.Job).filter_by(company_id=c.id, status="published").count()} for c in rows]


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
    if not (body.name or "").strip():
        raise HTTPException(400, "El nombre es obligatorio")
    if body.email and "@" not in body.email:
        raise HTTPException(400, "Email inválido")
    lead = models.Lead(name=body.name.strip()[:200], email=body.email.strip().lower()[:200],
                       phone=body.phone.strip()[:50], message=body.message.strip()[:4000],
                       type=body.type if body.type in ("contact", "business", "candidate", "support") else "contact")
    db.add(lead)
    models.log_event(db, "lead", f"{lead.type} {lead.email}")
    db.commit()
    return {"ok": True, "id": lead.id}
