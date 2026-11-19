from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..core.database import get_db
from ..services.social_importer import UnsafeTarget, parse_social_text, parse_url
from .deps import get_current_user, job_out

router = APIRouter(prefix="/social", tags=["social"])


class ImportIn(BaseModel):
    url: str = ""
    text: str = ""
    publish: bool = False


def _resolve(body: ImportIn) -> dict:
    if (body.url or "").strip():
        try:
            return parse_url(body.url)
        except UnsafeTarget as exc:
            raise HTTPException(400, f"URL no permitida: {exc}")
    if not (body.text or "").strip():
        raise HTTPException(400, "Envía una URL o el texto del post")
    return parse_social_text(body.text)


@router.post("/preview")
def preview(body: ImportIn):
    return _resolve(body)


@router.post("/import")
def import_social(body: ImportIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role not in ("business", "admin"):
        raise HTTPException(403, "Solo negocios pueden importar ofertas")
    draft = _resolve(body)
    if not user.company:
        if user.role == "admin":
            raise HTTPException(400, "El administrador debe tener una empresa para publicar")
        db.add(models.Company(user_id=user.id, name=user.name or "Mi empresa"))
        db.flush()
    if body.publish:
        draft["status"] = "published"
    job = models.Job(company_id=user.company.id, **draft)
    db.add(job)
    models.log_event(db, "social_import", draft.get("source_url", ""))
    db.commit()
    db.refresh(job)
    return job_out(job, db, viewer_id=user.id)
