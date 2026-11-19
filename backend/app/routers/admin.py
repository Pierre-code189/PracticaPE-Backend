from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..core.database import get_db
from ..core.security import dec_email, mask_email
from .deps import job_out, require_role

router = APIRouter(tags=["admin"])


@router.get("/admin/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    by_modality = dict(db.query(models.Job.modality, func.count(models.Job.id)).group_by(models.Job.modality).all())
    by_district = dict(db.query(models.Job.district, func.count(models.Job.id)).group_by(models.Job.district).all())
    by_role = dict(db.query(models.User.role, func.count(models.User.id)).group_by(models.User.role).all())
    by_status = dict(db.query(models.Job.status, func.count(models.Job.id)).group_by(models.Job.status).all())
    apps_by_day = [(str(d), c) for d, c in db.query(func.date(models.Application.created_at), func.count(models.Application.id))
                   .group_by(func.date(models.Application.created_at)).order_by(func.date(models.Application.created_at)).all()]
    return {
        "kpis": {"users": db.query(models.User).count(), "jobs": db.query(models.Job).count(),
                 "published": db.query(models.Job).filter_by(status="published").count(),
                 "drafts": db.query(models.Job).filter_by(status="draft").count(),
                 "applications": db.query(models.Application).count(),
                 "companies": db.query(models.Company).count(),
                 "leads": db.query(models.Lead).count(), "views": db.query(func.coalesce(func.sum(models.Job.views), 0)).scalar() or 0},
        "charts": {"by_modality": by_modality, "by_district": by_district, "by_role": by_role,
                   "by_status": by_status, "apps_by_day": apps_by_day},
    }


@router.get("/admin/users")
def users(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    rows = db.query(models.User).order_by(models.User.id.desc()).limit(200).all()
    return [{"id": u.id, "name": u.name, "email": dec_email(u.email_enc), "email_masked": mask_email(dec_email(u.email_enc)),
             "role": u.role, "is_active": u.is_active, "created_at": str(u.created_at),
             "company": u.company.name if u.company else ""} for u in rows]


class UserPatch(BaseModel):
    role: str = ""
    is_active: bool | None = None


@router.patch("/admin/users/{user_id}")
def update_user(user_id: int, body: UserPatch, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(404, "Usuario no encontrado")
    if body.role:
        if body.role not in ("candidate", "business", "admin"):
            raise HTTPException(400, "Rol inválido")
        if target.id == user.id and body.role != "admin":
            raise HTTPException(400, "No puedes quitarte el rol de administrador")
        target.role = body.role
    if body.is_active is not None:
        if target.id == user.id and not body.is_active:
            raise HTTPException(400, "No puedes desactivarte a ti mismo")
        target.is_active = body.is_active
    db.commit()
    return {"ok": True}


@router.get("/admin/companies")
def companies(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    rows = db.query(models.Company).order_by(models.Company.id.desc()).limit(200).all()
    return [{"id": c.id, "name": c.name, "sector": c.sector, "district": c.district,
             "is_public": c.is_public, "is_verified": c.is_verified,
             "jobs": db.query(models.Job).filter_by(company_id=c.id, status="published").count()}
            for c in rows]


class CompanyPatch(BaseModel):
    is_public: bool | None = None
    is_verified: bool | None = None


@router.patch("/admin/companies/{company_id}")
def update_company(company_id: int, body: CompanyPatch, db: Session = Depends(get_db),
                   user=Depends(require_role("admin"))):
    c = db.get(models.Company, company_id)
    if not c:
        raise HTTPException(404, "Empresa no encontrada")
    if body.is_public is not None:
        c.is_public = body.is_public
    if body.is_verified is not None:
        c.is_verified = body.is_verified
    db.commit()
    return {"ok": True}


@router.get("/admin/queue")
def queue(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    jobs = db.query(models.Job).filter_by(status="draft").order_by(models.Job.id.desc()).all()
    return [job_out(j, db, viewer_id=user.id) for j in jobs]


@router.patch("/admin/queue/{job_id}")
def review(job_id: int, action: str, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(404, "No encontrada")
    if action == "approve":
        job.status = "published"
    elif action == "reject":
        job.status = "closed"
    else:
        raise HTTPException(400, "action: approve|reject")
    db.commit()
    return {"ok": True, "status": job.status}


@router.get("/admin/otps")
def otps(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    rows = db.query(models.Otp).order_by(models.Otp.id.desc()).limit(50).all()
    return [{"id": o.id, "user_id": o.user_id,
             "email": mask_email(dec_email(o.user.email_enc)) if o.user else "",
             "expires_at": str(o.expires_at), "attempts": o.attempts, "used": o.used,
             "created_at": str(o.created_at)} for o in rows]


@router.get("/admin/leads")
def leads(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    rows = db.query(models.Lead).order_by(models.Lead.id.desc()).limit(100).all()
    return [{"id": l.id, "name": l.name, "email": l.email, "phone": l.phone,
             "message": l.message, "type": l.type, "status": l.status, "created_at": str(l.created_at)} for l in rows]


class LeadPatch(BaseModel):
    status: str


@router.patch("/admin/leads/{lead_id}")
def lead_status(lead_id: int, body: LeadPatch, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    lead = db.get(models.Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead no encontrado")
    if body.status not in ("new", "contacted", "closed"):
        raise HTTPException(400, "Estado inválido")
    lead.status = body.status
    db.commit()
    return {"ok": True}
