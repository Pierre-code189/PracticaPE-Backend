"""Dependencias de FastAPI: sesión de BD, usuario actual y roles."""
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import decode_token
from ..models import User


def current_user(request: Request, authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta el token de acceso")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o vencido")
    try:
        uid = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido")
    user = db.query(User).filter(User.id == uid).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Cuenta no disponible")
    return user


def optional_user(request: Request, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Usuario si hay token válido; None si no lo hay. Para rutas semipúblicas."""
    if not authorization.startswith("Bearer "):
        return None
    payload = decode_token(authorization.split(" ", 1)[1].strip())
    if not payload:
        return None
    try:
        uid = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    user = db.query(User).filter(User.id == uid).first()
    if not user or not user.is_active:
        return None
    return user


def require_role(*roles: str):
    def _dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="No tienes permiso para esta acción")
        return user
    return _dep


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
