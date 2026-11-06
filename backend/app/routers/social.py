from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.database import get_db
from .. import models
from ..services.social_importer import parse_social_text, parse_url
from .deps import get_current_user, job_out

router = APIRouter(prefix="/social", tags=["social"])


class ImportIn(BaseModel):
    url: str = ""
    text: str = ""
    publish: bool = False


@router.post("/preview")
def preview(body: ImportIn):
    if body.url:
        return parse_url(body.url)
    return parse_social_text(body.text, body.url)


@router.post("/import")
def import_social(body: ImportIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role not in ("business", "admin"):
        raise HTTPException(403, "Solo negocios pueden importar ofertas")
    if not user.company:
        db.add(models.Company(user_id=user.id, name=user.name))
        db.flush()
    draft = parse_url(body.url) if body.url else parse_social_text(body.text)
    if body.publish:
        draft["status"] = "published"
    job = models.Job(company_id=user.company.id, **draft)
    db.add(job)
    models.log_event(db, "social_import", draft.get("source_url", ""))
    db.commit()
    db.refresh(job)
    return job_out(job, db, viewer_id=user.id)
