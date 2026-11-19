import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

url = settings.database_url
connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
if url.startswith("sqlite"):
    path = url.replace("sqlite:///", "")
    if path and path != ":memory:":
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
engine = create_engine(url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_users_email(conn) -> None:
    """Migración idempotente: cifra el email (CI03) y deja un alias no identificable.

    - Añade `email_hash` / `email_enc` si no existen.
    - Para cada fila con email legible y sin cifrar: cifra, calcula el hash y
      sustituye `email` por un alias que no revela el dato real.
    """
    cols = {r[1] for r in conn.execute(text("PRAGMA table_info(users)"))}
    if "email_hash" not in cols:
        conn.execute(text("ALTER TABLE users ADD COLUMN email_hash VARCHAR(64)"))
    if "email_enc" not in cols:
        conn.execute(text("ALTER TABLE users ADD COLUMN email_enc TEXT DEFAULT ''"))

    from .security import email_hash, enc_email

    filas = conn.execute(text("SELECT id, email, email_hash, email_enc FROM users")).fetchall()
    for uid, email, ehash, eenc in filas:
        real = email or ""
        if eenc or not real:
            continue
        conn.execute(
            text("UPDATE users SET email_enc=:e, email_hash=:h, email=:alias WHERE id=:i"),
            {"e": enc_email(real), "h": email_hash(real), "alias": f"u{uid}@oculto.local", "i": uid},
        )
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_hash ON users(email_hash)"))
    conn.commit()


def init_db():
    from .. import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    if settings.database_url.startswith("sqlite"):
        with engine.begin() as conn:
            _migrate_users_email(conn)
