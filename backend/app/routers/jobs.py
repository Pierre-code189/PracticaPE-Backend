from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..core.config import settings
from ..core.database import get_db
from ..core.security import dec_email
from .deps import get_current_user, get_optional_user, job_out, notify

router = APIRouter(prefix="/jobs", tags=["jobs"])

JOB_STATUSES = ("draft", "published", "closed")
MODALITIES = ("presencial", "remoto", "hibrido")


class JobIn(BaseModel):
    title: str = ""
    description: str = ""
    modality: str = "presencial"
    district: str = "Piura"
    city: str = "Piura"
    lat: float = None
    lng: float = None
    salary: str = ""
    positions: int = 1
    status: str = "draft"
    source_url: str = ""


class ApplyIn(BaseModel):
    message: str = ""


class StatusIn(BaseModel):
    status: str


def _get_job(db, job_id):
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(404, "Oferta no encontrada")
    return job


def _is_owner(user, job) -> bool:
    """Admin siempre; empresa solo si la oferta es suya."""
    if user.role == "admin":
        return True
    return bool(user.company and job.company_id == user.company.id)


def _clean_in(body: JobIn) -> dict:
    data = body.model_dump()
    if not (data.get("title") or "").strip():
        raise HTTPException(400, "El título es obligatorio")
    data["title"] = data["title"].strip()[:180]
    data["description"] = (data.get("description") or "").strip()[:4000]
    if data.get("modality") not in MODALITIES:
        data["modality"] = "presencial"
    if data.get("status") not in JOB_STATUSES:
        raise HTTPException(400, "Estado inválido")
    try:
        data["positions"] = max(1, int(data.get("positions") or 1))
    except (TypeError, ValueError):
        data["positions"] = 1
    return data


@router.get("")
def list_jobs(modality: str = "", district: str = "", city: str = "", q: str = "",
              company_id: int = 0, status: str = "",
              db: Session = Depends(get_db), user=Depends(get_optional_user)):
    # Los borradores nunca son públicos (VU02): sin estado explícito se lista published.
    if not status:
        status = "published"
    if status != "published":
        if not user:
            return []
        if user.role != "admin":
            raise HTTPException(403, "No autorizado")
    query = db.query(models.Job).filter(models.Job.status == status)
    if modality:
        query = query.filter(models.Job.modality == modality)
    if district:
        query = query.filter(models.Job.district == district)
    if city:
        query = query.filter(models.Job.city == city)
    if company_id:
        query = query.filter(models.Job.company_id == company_id)
    if q:
        term = (q or "").strip()[:120]
        query = query.filter(models.Job.title.ilike(f"%{term}%") | models.Job.description.ilike(f"%{term}%"))
    jobs = query.order_by(models.Job.id.desc()).limit(200).all()
    return [job_out(j, db, viewer_id=user.id if user else None) for j in jobs]


@router.get("/map")
def jobs_map(db: Session = Depends(get_db)):
    jobs = db.query(models.Job).filter(models.Job.status == "published", models.Job.lat.isnot(None)).all()
    return [{"id": j.id, "title": j.title, "lat": j.lat, "lng": j.lng, "district": j.district,
             "modality": j.modality} for j in jobs]


@router.get("/districts")
def districts():
    return settings.piura_districts


@router.get("/saved/mine")
def my_saved(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(models.SavedJob).filter_by(candidate_id=user.id).all()
    return [job_out(r.job, db, viewer_id=user.id) for r in rows]


@router.post("")
def create_job(body: JobIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role not in ("business", "admin"):
        raise HTTPException(403, "Solo negocios pueden crear ofertas")
    if not user.company:
        if user.role == "admin":
            raise HTTPException(400, "El administrador debe tener una empresa para publicar")
        db.add(models.Company(user_id=user.id, name=user.name or "Mi empresa"))
        db.flush()
    job = models.Job(company_id=user.company.id, **_clean_in(body))
    db.add(job)
    models.log_event(db, "job_created", job.title)
    db.commit()
    db.refresh(job)
    return job_out(job, db, viewer_id=user.id)


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db), user=Depends(get_optional_user)):
    job = _get_job(db, job_id)
    # Un borrador solo lo ven su dueño y el admin (VU01).
    if job.status != "published" and not (user and _is_owner(user, job)):
        raise HTTPException(404, "Oferta no encontrada")
    job.views += 1
    db.commit()
    applied = bool(user and db.query(models.Application).filter_by(
        job_id=job.id, candidate_id=user.id).first())
    reveal = bool(user and (_is_owner(user, job) or applied))
    return job_out(job, db, viewer_id=user.id if user else None, reveal_contact=reveal)


@router.put("/{job_id}")
def update_job(job_id: int, body: JobIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    job = _get_job(db, job_id)
    if not _is_owner(user, job):
        raise HTTPException(403, "No autorizado")
    for k, v in _clean_in(body).items():
        setattr(job, k, v)
    db.commit()
    return job_out(job, db, viewer_id=user.id)


@router.patch("/{job_id}/status")
def set_status(job_id: int, body: StatusIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    job = _get_job(db, job_id)
    if not _is_owner(user, job):
        raise HTTPException(403, "No autorizado")
    if body.status not in JOB_STATUSES:
        raise HTTPException(400, "Estado inválido")
    job.status = body.status
    db.commit()
    return {"ok": True, "status": job.status}


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    job = _get_job(db, job_id)
    if not _is_owner(user, job):
        raise HTTPException(403, "No autorizado")
    db.delete(job)
    db.commit()
    return {"ok": True}


@router.post("/{job_id}/apply")
def apply(job_id: int, body: ApplyIn = ApplyIn(), db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role != "candidate":
        raise HTTPException(403, "Solo candidatos pueden postular")
    job = _get_job(db, job_id)
    if job.status != "published":
        raise HTTPException(400, "La oferta no está publicada")
    existing = db.query(models.Application).filter_by(job_id=job_id, candidate_id=user.id).first()
    if existing:
        raise HTTPException(400, "Ya postulaste a esta oferta (postulación única)")
    app = models.Application(job_id=job_id, candidate_id=user.id, message=(body.message or "").strip()[:2000])
    db.add(app)
    models.log_event(db, "application", f"job={job_id} candidate={user.id}")
    if job.company:
        notify(db, job.company.user_id, "application", "Nueva postulación",
               f"{user.name or 'Un candidato'} postuló a '{job.title}'", f"#/job/{job_id}")
    db.commit()
    return {"ok": True, "application_id": app.id, "status": app.status}


@router.post("/{job_id}/save")
def save(job_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    job = _get_job(db, job_id)
    if job.status != "published":
        raise HTTPException(400, "La oferta no está publicada")
    if not db.query(models.SavedJob).filter_by(job_id=job_id, candidate_id=user.id).first():
        db.add(models.SavedJob(job_id=job_id, candidate_id=user.id))
        db.commit()
    return {"ok": True}


@router.delete("/{job_id}/save")
def unsave(job_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = db.query(models.SavedJob).filter_by(job_id=job_id, candidate_id=user.id).first()
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.get("/{job_id}/applicants")
def applicants(job_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    job = _get_job(db, job_id)
    if not _is_owner(user, job):
        raise HTTPException(403, "No autorizado")
    apps = db.query(models.Application).filter_by(job_id=job_id).all()
    out = []
    for a in apps:
        c = db.query(models.User).filter_by(id=a.candidate_id).first()
        prof = c.candidate if c else None
        out.append({"id": a.id, "candidate_id": a.candidate_id, "message": a.message,
                    "status": a.status, "created_at": str(a.created_at),
                    "candidate": {"name": c.name if c else "", "email": dec_email(c.email_enc) if c else "",
                                  "headline": prof.headline if prof else "",
                                  "skills": prof.skills if prof else ""}})
    return out


@router.patch("/{job_id}/applicants/{app_id}")
def change_status(job_id: int, app_id: int, body: StatusIn, db: Session = Depends(get_db),
                  user=Depends(get_current_user)):
    job = _get_job(db, job_id)
    if not _is_owner(user, job):
        raise HTTPException(403, "No autorizado")
    if body.status not in ("applied", "reviewed", "accepted", "rejected"):
        raise HTTPException(400, "Estado inválido")
    app = db.get(models.Application, app_id)
    if not app or app.job_id != job_id:
        raise HTTPException(404, "Postulación no encontrada")
    app.status = body.status
    notify(db, app.candidate_id, "application_status", "Actualización de postulación",
           f"Tu postulación a '{job.title}' pasó a: {body.status}", f"#/job/{job_id}")
    db.commit()
    return {"ok": True, "status": body.status}
