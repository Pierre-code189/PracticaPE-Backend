"""Crea (o promociona) un administrador.

Uso:
  python scripts/create_admin.py correo@dominio.com
  python scripts/create_admin.py correo@dominio.com --name "Nombre"

El correo queda cifrado en BD; el rol se lee del email real.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.security import email_alias, email_hash_of, encrypt_email  # noqa: E402
from app.models import CandidateProfile, User  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/create_admin.py correo@dominio.com [--name Nombre]")
        return 2
    email = sys.argv[1].strip().lower()
    name = "Administrador"
    if "--name" in sys.argv:
        name = sys.argv[sys.argv.index("--name") + 1]

    init_db()
    db = SessionLocal()
    try:
        h = email_hash_of(email)
        u = db.query(User).filter(User.email_hash == h).first()
        if not u:
            u = User(email=email_alias(0), email_hash=h, email_enc=encrypt_email(email),
                     name=name, role="admin")
            db.add(u)
            db.flush()
            u.email = email_alias(u.id)
            db.add(CandidateProfile(user_id=u.id))
        else:
            u.role = "admin"
            if not u.email_enc:
                u.email_enc = encrypt_email(email)
            if not u.name:
                u.name = name
        db.commit()
        print("admin listo: id=%d rol=%s nombre=%s" % (u.id, u.role, u.name))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
