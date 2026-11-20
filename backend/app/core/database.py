"""Base de datos: SQLite con foreign keys, WAL y migración idempotente."""
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    future=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crea las tablas y migra datos legados. Idempotente."""
    from .. import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_users_email()


def _migrate_users_email():
    """Cifra los correos legados en claro (CI03). No falla si ya están cifrados."""
    from .security import email_hash_of
    from ..models import User

    db = SessionLocal()
    try:
        pendientes = db.query(User).filter(User.email_hash.is_(None)).all()
        for u in pendientes:
            raw = u.email or ""
            if not raw or raw.endswith("@oculto.local"):
                u.email_hash = email_hash_of(raw)
                u.email = "u%d@oculto.local" % u.id
                continue
            u.email_hash = email_hash_of(raw)
            u.email = "u%d@oculto.local" % u.id
        db.commit()
    finally:
        db.close()
