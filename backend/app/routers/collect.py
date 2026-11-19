from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.database import get_db
from .. import models
from ..services import web_collector
from .deps import require_role, job_out

router = APIRouter(prefix="/collect", tags=["collect"])


class RunIn(BaseModel):
    query: str = "empleos Piura"
    max_results: int = 10
    publish: bool = False


@router.post("/run")
def run(body: RunIn, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    drafts = web_collector.collect_search(body.query, body.max_results)
    created = 0
    for d in drafts:
        if d.get("source_url") and db.query(models.Job).filter_by(source_url=d["source_url"]).first():
            continue
        if body.publish:
            d["status"] = "published"
        db.add(models.Job(company_id=None, **d))
        created += 1
    models.log_event(db, "collector_run", f"{body.query} created={created}")
    db.commit()
    return {"ok": True, "found": len(drafts), "created": created}


@router.get("/status")
def status(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    drafts = db.query(models.Job).filter_by(status="draft").count()
    total = db.query(models.Job).count()
    return {"drafts": drafts, "total_jobs": total}


@router.get("/jobs")
def collected(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    jobs = db.query(models.Job).filter(models.Job.source.in_(["web", "social"])).order_by(models.Job.id.desc()).limit(100).all()
    return [job_out(j, db, viewer_id=user.id) for j in jobs]
