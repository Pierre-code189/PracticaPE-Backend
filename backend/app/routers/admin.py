"""Panel de administración: KPIs, cola de moderación, usuarios y leads."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import Application, Company, Job, Lead, User
from ..routers.deps import require_role

router = APIRouter(tags=["admin"])


@router.get("/admin/dashboard")
def dashboard(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return {
        "users": db.query(User).count(),
        "candidates": db.query(User).filter(User.role == "candidate").count(),
        "business": db.query(User).filter(User.role == "business").count(),
        "companies": db.query(Company).count(),
        "jobs_published": db.query(Job).filter(Job.status == "published").count(),
        "jobs_draft": db.query(Job).filter(Job.status == "draft").count(),
        "jobs_closed": db.query(Job).filter(Job.status == "closed").count(),
        "queue": db.query(Job).filter(Job.status == "pending").count(),
        "applications": db.query(Application).count(),
        "leads": db.query(Lead).count(),
        "verified_companies": db.query(Company).filter(Company.is_verified.is_(True)).count(),
    }


@router.get("/admin/queue")
def queue(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = db.query(Job).filter(Job.status == "pending").order_by(Job.id.desc()).all()
    return {"items": [
        {
            "id": j.id, "title": j.title, "description": j.description,
            "category": j.category, "modality": j.modality, "district": j.district,
            "salary": j.salary, "positions": j.positions, "status": j.status,
            "company_name": (j.company.name if j.company else "") or "",
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in rows
    ]}


@router.patch("/admin/queue/{job_id}")
def moderate(job_id: int, action: str = Query(""), user: User = Depends(require_role("admin")),
             db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    if action == "approve":
        j.status = "published"
    elif action == "reject":
        j.status = "rejected"
    else:
        raise HTTPException(status_code=400, detail="Acción no válida")
    db.commit()
    return {"ok": True, "status": j.status}


@router.get("/admin/users")
def users(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = db.query(User).order_by(User.id.desc()).limit(200).all()
    return {"items": [
        {
            "id": u.id, "name": u.name, "role": u.role, "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in rows
    ]}


@router.get("/admin/leads")
def leads(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = db.query(Lead).order_by(Lead.id.desc()).limit(200).all()
    return {"items": [
        {
            "id": l.id, "name": l.name, "email": l.email, "phone": l.phone,
            "message": l.message, "type": l.type, "status": l.status,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in rows
    ]}


@router.patch("/admin/users/{user_id}")
def toggle_user(user_id: int, active: bool = Query(True), user: User = Depends(require_role("admin")),
                db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    target.is_active = active
    db.commit()
    return {"ok": True, "is_active": target.is_active}
