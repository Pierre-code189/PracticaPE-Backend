"""Perfil de candidato: propio (GET/PUT), items y foto de perfil."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..models import CandidateProfile, Photo, ProfileItem, User
from ..routers.deps import current_user, require_role

router = APIRouter(tags=["profile"])


def _profile(p: CandidateProfile, email: str) -> dict:
    return {
        "id": p.id,
        "user_id": p.user_id,
        "email": email,
        "name": "",
        "headline": p.headline,
        "summary": p.summary,
        "city": p.city,
        "district": p.district,
        "phone": p.phone,
        "skills": [s for s in (p.skills or "").split(",") if s.strip()],
        "avatar_url": p.avatar_url,
        "cover_url": p.cover_url,
        "items": [
            {"id": i.id, "kind": i.kind, "title": i.title, "org": i.org,
             "start": i.start, "end": i.end, "description": i.description, "location": i.location}
            for i in p.items
        ],
        "photos": [{"id": x.id, "url": x.url, "caption": x.caption, "kind": x.kind} for x in p.photos],
    }


@router.get("/me/profile")
def my_profile(user: User = Depends(require_role("candidate", "business")), db: Session = Depends(get_db)):
    p = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    if not p:
        p = CandidateProfile(user_id=user.id)
        db.add(p)
        db.commit()
        db.refresh(p)
    return _profile(p, _email(user, db))


def _email(user: User, db: Session) -> str:
    from ..core.security import decrypt_email
    return decrypt_email(user.email_enc)


class ProfileIn(BaseModel):
    headline: str = ""
    summary: str = ""
    city: str = "Piura"
    district: str = "Piura"
    phone: str = ""
    skills: list = []
    avatar_url: str = ""
    cover_url: str = ""


@router.put("/me/profile")
def save_profile(body: ProfileIn, user: User = Depends(require_role("candidate")), db: Session = Depends(get_db)):
    p = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    if not p:
        p = CandidateProfile(user_id=user.id)
        db.add(p)
    p.headline = body.headline.strip()
    p.summary = body.summary.strip()
    p.city = body.city.strip() or "Piura"
    p.district = body.district.strip() or "Piura"
    p.phone = body.phone.strip()
    p.skills = ",".join([s.strip() for s in (body.skills or []) if s.strip()])[:1000]
    if body.avatar_url:
        p.avatar_url = body.avatar_url.strip()[:500]
    if body.cover_url:
        p.cover_url = body.cover_url.strip()[:500]
    db.commit()
    db.refresh(p)
    return _profile(p, _email(user, db))


class ItemIn(BaseModel):
    kind: str = "experience"
    title: str = ""
    org: str = ""
    start: str = ""
    end: str = ""
    description: str = ""
    location: str = ""


@router.post("/me/profile/items")
def add_item(body: ItemIn, user: User = Depends(require_role("candidate")), db: Session = Depends(get_db)):
    p = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    if not p:
        raise HTTPException(status_code=400, detail="Crea primero tu perfil")
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="El título es obligatorio")
    item = ProfileItem(profile_id=p.id, kind=body.kind, title=body.title.strip(), org=body.org.strip(),
                       start=body.start.strip(), end=body.end.strip(),
                       description=body.description.strip(), location=body.location.strip())
    db.add(item)
    db.commit()
    return {"ok": True, "id": item.id}


@router.delete("/me/profile/items/{item_id}")
def delete_item(item_id: int, user: User = Depends(require_role("candidate")), db: Session = Depends(get_db)):
    p = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    item = db.query(ProfileItem).filter(ProfileItem.id == item_id, ProfileItem.profile_id == (p.id if p else -1)).first()
    if not item:
        raise HTTPException(status_code=404, detail="Elemento no encontrado")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/me/cv")
async def upload_cv(file: UploadFile = File(...), user: User = Depends(require_role("candidate")),
                   db: Session = Depends(get_db)):
    import os
    ct = (file.content_type or "").lower()
    if ct not in settings.upload_allow:
        raise HTTPException(status_code=400, detail="Formato no permitido")
    data = await file.read()
    if len(data) > settings.upload_max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande")
    os.makedirs(settings.upload_dir, exist_ok=True)
    name = "cv_%d_%s" % (user.id, file.filename.replace("/", "_")[-80:])
    path = os.path.join(settings.upload_dir, name)
    with open(path, "wb") as fh:
        fh.write(data)
    return {"ok": True, "file": name, "bytes": len(data)}


@router.get("/profiles/{user_id}")
def public_profile(user_id: int, db: Session = Depends(get_db)):
    """Perfil público: solo lo que el candidato decidió compartir."""
    p = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not p:
        return {"detail": "Perfil no encontrado"}
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return {"detail": "Perfil no encontrado"}
    return {
        "id": p.id,
        "user_id": p.user_id,
        "name": u.name,
        "headline": p.headline,
        "summary": p.summary,
        "city": p.city,
        "district": p.district,
        "skills": [s for s in (p.skills or "").split(",") if s.strip()],
        "avatar_url": p.avatar_url,
        "items": [
            {"id": i.id, "kind": i.kind, "title": i.title, "org": i.org,
             "start": i.start, "end": i.end, "description": i.description, "location": i.location}
            for i in p.items
        ],
        "photos": [{"id": x.id, "url": x.url, "caption": x.caption} for x in p.photos if x.kind == "gallery"],
    }
