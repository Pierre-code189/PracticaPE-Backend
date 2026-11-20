"""Ofertas: listado público, detalle, postulación, guardado y alta por empresa."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import Application, Job, SavedJob, User
from ..routers.deps import optional_user, require_role
from ..services.social_importer import UnsafeTarget, parse_social_text, parse_url

router = APIRouter(tags=["jobs"])


class SubmitIn(BaseModel):
    url: str = ""
    text: str = ""
    title: str = ""


def _public_job(j: Job) -> dict:
    comp = j.company
    return {
        "id": j.id,
        "title": j.title,
        "description": j.description,
        "category": j.category,
        "modality": j.modality,
        "district": j.district,
        "city": j.city,
        "lat": j.lat,
        "lng": j.lng,
        "salary": j.salary,
        "positions": j.positions,
        "status": j.status,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "views": j.views,
        "company_name": (comp.name if comp else "") or "",
        "company_logo": (comp.logo_url if comp else "") or "",
        "company_verified": bool(comp and comp.is_verified),
        "source": j.source or "manual",
        "source_url": j.source_url or "",
    }


def _visible(db: Session, job_id: int, user):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    if job.status != "published":
        if user is None:
            raise HTTPException(status_code=404, detail="Oferta no encontrada")
        if user.role == "candidate":
            raise HTTPException(status_code=404, detail="Oferta no encontrada")
        if user.role == "business":
            if not job.company or job.company.user_id != user.id:
                raise HTTPException(status_code=403, detail="No es tu oferta")
        elif user.role != "admin":
            raise HTTPException(status_code=403, detail="Sin permiso")
    return job


@router.get("/jobs")
def list_jobs(
    q: str = "",
    district: str = "",
    modality: str = "",
    category: str = "",
    source: str = "",
    salary_min: int = 0,
    salary_max: int = 0,
    status: str = "",
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(optional_user),
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    # visibilidad: anónimo y candidato solo ven publicadas, SIEMPRE
    if not user or user.role == "candidate":
        query = query.filter(Job.status == "published")
    elif user.role == "business":
        own = query.filter(Job.company.has(user_id=user.id))
        if status:
            own = own.filter(Job.status == status)
        query = own
    elif user.role == "admin":
        if status:
            query = query.filter(Job.status == status)

    if q:
        like = "%" + q.strip().lower() + "%"
        query = query.filter(
            (Job.title.ilike(like)) | (Job.description.ilike(like)) | (Job.category.ilike(like))
        )
    if district:
        query = query.filter(Job.district.ilike(district))
    if modality:
        query = query.filter(Job.modality == modality)
    if category:
        query = query.filter(Job.category == category)
    if source == 'manual':
        # 'Empresas' agrupa los avisos publicados desde el panel y los sembrados
        query = query.filter(Job.source.in_(["manual", "seed"]))
    elif source:
        query = query.filter(Job.source == source)

    total = query.count()
    items = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()

    def sal(j):
        try:
            return float(str(j.salary).replace("S/", "").replace(",", "").strip() or 0)
        except (TypeError, ValueError):
            return 0.0

    if salary_min or salary_max:
        items = [j for j in items if (not salary_min or sal(j) >= salary_min) and (not salary_max or sal(j) <= salary_max)]
        total = len(items)

    return {"total": total, "items": [_public_job(j) for j in items]}


@router.get("/jobs/sources")
def job_sources(user: User = Depends(optional_user), db: Session = Depends(get_db)):
    """Recuento por fuente del feed (web | user | manual)."""
    q = db.query(Job.status, Job.source, func.count(Job.id))
    if not user or user.role == "candidate":
        q = q.filter(Job.status == "published")
    rows = q.group_by(Job.status, Job.source).all()
    out = {}
    for st, src, n in rows:
        key = src or "manual"
        slot = out.setdefault(key, {"total": 0, "published": 0, "draft": 0, "pending": 0})
        slot["total"] += n
        if st in slot:
            slot[st] += n
    return {"sources": out}


@router.post("/jobs/submit")
def submit_job(
    body: "SubmitIn",
    user: User = Depends(require_role("candidate", "business", "admin")),
    db: Session = Depends(get_db),
):
    """Envío de una oferta por enlace o texto ("Publica tu chamba").

    Nunca se publica sola: queda en revisión (pending) para moderación.
    """
    url = (body.url or "").strip()
    text = (body.text or "").strip()
    if not url and not text:
        raise HTTPException(status_code=400, detail="Envía el enlace o el texto de la oferta")
    try:
        draft = parse_url(url) if url else parse_social_text(text or body.title, "")
    except UnsafeTarget as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer esa oferta")
    if body.title and len(body.title.strip()) > 4:
        draft["title"] = body.title.strip()[:180]
    draft["source"] = "user"
    draft["source_url"] = url[:500]
    draft["status"] = "pending"
    job = Job(
        company_id=None,
        title=draft.get("title", "")[:255] or "Oferta enviada",
        description=draft.get("description", "")[:4000],
        modality=draft.get("modality", "presencial"),
        district=draft.get("district", "Piura"),
        city=draft.get("city", "Piura"),
        lat=draft.get("lat"), lng=draft.get("lng"),
        salary=draft.get("salary", "")[:100],
        status="pending",
        source="user",
        source_url=draft["source_url"],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"ok": True, "id": job.id, "status": "pending",
            "message": "Oferta enviada a revisión. La publicaremos tras verificarla."}


@router.get("/jobs/districts")
def districts(user: User = Depends(optional_user), db: Session = Depends(get_db)):
    from ..core.config import settings
    rows = [r[0] for r in db.query(Job.district).filter(Job.district != "").distinct().all()]
    base = [d for d in settings.piura_districts if d not in rows]
    return {"districts": base + sorted(rows)}


@router.get("/jobs/map")
def job_map(
    district: str = "",
    modality: str = "",
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(optional_user),
    db: Session = Depends(get_db),
):
    query = db.query(Job).filter(Job.status == "published", Job.lat.isnot(None), Job.lng.isnot(None))
    if district:
        query = query.filter(Job.district.ilike(district))
    if modality:
        query = query.filter(Job.modality == modality)
    return {"items": [_public_job(j) for j in query.limit(limit).all()]}


@router.get("/jobs/saved/mine")
def saved_mine(user: User = Depends(require_role("candidate", "business")), db: Session = Depends(get_db)):
    rows = db.query(SavedJob).filter(SavedJob.candidate_id == user.id).order_by(SavedJob.id.desc()).all()
    out = []
    for s in rows:
        j = s.job
        if j:
            item = _public_job(j)
            item["saved_at"] = s.created_at.isoformat() if s.created_at else None
            out.append(item)
    return {"items": out}


@router.post("/jobs/{job_id}/save")
def save_job(job_id: int, user: User = Depends(require_role("candidate", "business")), db: Session = Depends(get_db)):
    job = _visible(db, job_id, user)
    exists = db.query(SavedJob).filter(SavedJob.job_id == job.id, SavedJob.candidate_id == user.id).first()
    if exists:
        return {"ok": True, "saved": True}
    db.add(SavedJob(job_id=job.id, candidate_id=user.id))
    db.commit()
    return {"ok": True, "saved": True}


@router.delete("/jobs/{job_id}/save")
def unsave_job(job_id: int, user: User = Depends(require_role("candidate", "business")), db: Session = Depends(get_db)):
    row = db.query(SavedJob).filter(SavedJob.job_id == job_id, SavedJob.candidate_id == user.id).first()
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True, "saved": False}


@router.get("/jobs/{job_id}")
def get_job(job_id: int, user: User = Depends(optional_user), db: Session = Depends(get_db)):
    job = _visible(db, job_id, user)
    data = _public_job(job)
    if user and user.role == "candidate":
        app = db.query(Application).filter(Application.job_id == job.id, Application.candidate_id == user.id).first()
        data["my_application"] = None
        if app:
            data["my_application"] = {
                "id": app.id, "status": app.status,
                "created_at": app.created_at.isoformat() if app.created_at else None,
            }
    return data


@router.post("/jobs/{job_id}/apply")
def apply_job(
    job_id: int,
    payload: dict = None,
    user: User = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
):
    job = _visible(db, job_id, user)
    if job.status != "published":
        raise HTTPException(status_code=400, detail="Esta oferta ya no está disponible")
    dup = db.query(Application).filter(Application.job_id == job.id, Application.candidate_id == user.id).first()
    if dup:
        raise HTTPException(status_code=409, detail="Ya te postulaste a esta oferta")
    app = Application(job_id=job.id, candidate_id=user.id, message=(payload or {}).get("message", ""))
    db.add(app)
    db.commit()
    return {"ok": True, "application_id": app.id, "status": app.status}


@router.get("/jobs/{job_id}/applicants")
def applicants(job_id: int, user: User = Depends(require_role("business", "admin")), db: Session = Depends(get_db)):
    job = _visible(db, job_id, user)
    if user.role == "business" and (not job.company or job.company.user_id != user.id):
        raise HTTPException(status_code=403, detail="No es tu oferta")
    rows = db.query(Application).filter(Application.job_id == job.id).order_by(Application.id.desc()).all()
    return {"items": [
        {
            "id": a.id,
            "candidate_id": a.candidate_id,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]}


@router.post("/jobs")
def create_job(payload: dict, user: User = Depends(require_role("business", "admin")), db: Session = Depends(get_db)):
    comp = user.company
    if not comp:
        raise HTTPException(status_code=400, detail="Completa primero el perfil de empresa")
    job = Job(
        company_id=comp.id,
        title=str(payload.get("title", "")).strip(),
        description=str(payload.get("description", "")).strip(),
        category=str(payload.get("category", "")).strip(),
        modality=str(payload.get("modality", "presencial")).strip(),
        district=str(payload.get("district", "Piura")).strip(),
        city=str(payload.get("city", "Piura")).strip(),
        salary=str(payload.get("salary", "")).strip(),
        positions=int(payload.get("positions") or 1),
        status=str(payload.get("status", "draft")),
        source="manual",
    )
    if not job.title:
        raise HTTPException(status_code=400, detail="El título es obligatorio")
    db.add(job)
    db.commit()
    db.refresh(job)
    return _public_job(job)


@router.put("/jobs/{job_id}")
def update_job(job_id: int, payload: dict, user: User = Depends(require_role("business", "admin")), db: Session = Depends(get_db)):
    job = _visible(db, job_id, user)
    if user.role == "business" and (not job.company or job.company.user_id != user.id):
        raise HTTPException(status_code=403, detail="No es tu oferta")
    for field in ("title", "description", "category", "modality", "district", "city", "salary"):
        if field in payload:
            setattr(job, field, str(payload[field]).strip())
    if "positions" in payload:
        job.positions = int(payload["positions"] or 1)
    if "status" in payload and payload["status"] in ("draft", "published", "closed"):
        job.status = payload["status"]
    db.commit()
    db.refresh(job)
    return _public_job(job)


@router.post("/jobs/{job_id}/close")
def close_job(job_id: int, user: User = Depends(require_role("business", "admin")), db: Session = Depends(get_db)):
    job = _visible(db, job_id, user)
    if user.role == "business" and (not job.company or job.company.user_id != user.id):
        raise HTTPException(status_code=403, detail="No es tu oferta")
    job.status = "closed"
    db.commit()
    return {"ok": True, "status": job.status}
