from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..core.database import get_db
from .. import models
from .deps import get_current_user, require_role, job_out

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
    return [{"id": o.id, "user_id": o.user_id, "email": o.user.email if o.user else "",
             "expires_at": str(o.expires_at), "attempts": o.attempts, "used": o.used,
             "created_at": str(o.created_at)} for o in rows]


@router.get("/admin/leads")
def leads(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    rows = db.query(models.Lead).order_by(models.Lead.id.desc()).limit(100).all()
    return [{"id": l.id, "name": l.name, "email": l.email, "phone": l.phone,
             "message": l.message, "type": l.type, "status": l.status, "created_at": str(l.created_at)} for l in rows]


@router.patch("/admin/leads/{lead_id}")
def lead_status(lead_id: int, status: str, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    lead = db.get(models.Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead no encontrado")
    lead.status = status
    db.commit()
    return {"ok": True}
