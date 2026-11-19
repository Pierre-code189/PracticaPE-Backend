"""Create/ensure an admin user. Usage: python scripts/create_admin.py [email]"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.database import SessionLocal, init_db
from app.core.security import email_hash, enc_email
from app import models

init_db()
email = sys.argv[1] if len(sys.argv) > 1 else "admin@practicape.pe"
db = SessionLocal()
h = email_hash(email)
u = db.query(models.User).filter(models.User.email_hash == h).first()
if not u:
    u = models.User(email="u0@oculto.local", email_hash=h, email_enc=enc_email(email),
                    name="Admin", role="admin")
    db.add(u); db.flush()
    u.email = f"u{u.id}@oculto.local"
else:
    u.role = "admin"
db.commit()
print(f"Admin OK: {email} (id={u.id}) — login vía OTP en /#/auth")
db.close()
