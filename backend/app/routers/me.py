"""Postulaciones del candidato y notificaciones."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import Application, Job, Notification, User
from ..routers.deps import require_role

router = APIRouter(tags=["me"])


@router.get("/me/applications")
def my_applications(user: User = Depends(require_role("candidate", "business")), db: Session = Depends(get_db)):
    rows = db.query(Application).filter(Application.candidate_id == user.id).order_by(Application.id.desc()).all()
    out = []
    for a in rows:
        j = db.query(Job).filter(Job.id == a.job_id).first()
        if not j:
            continue
        out.append({
            "id": a.id,
            "job_id": j.id,
            "title": j.title,
            "company_name": (j.company.name if j.company else "") or "",
            "district": j.district,
            "modality": j.modality,
            "salary": j.salary,
            "status": a.status,
            "message": a.message,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return {"items": out}


@router.get("/me/notifications")
def my_notifications(user: User = Depends(require_role("candidate", "business")), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(50).all()
    return {"items": [
        {
            "id": n.id, "type": n.type, "title": n.title, "body": n.body,
            "link": n.link, "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]}


@router.patch("/me/notifications/{notif_id}/read")
def mark_read(notif_id: int, user: User = Depends(require_role("candidate", "business")), db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == notif_id, Notification.user_id == user.id).first()
    if not n:
        return {"ok": True}
    n.is_read = True
    db.commit()
    return {"ok": True}
