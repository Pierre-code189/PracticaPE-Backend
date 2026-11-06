"""Create/ensure an admin user. Usage: python scripts/create_admin.py [email]"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.database import SessionLocal, init_db
from app import models

init_db()
email = sys.argv[1] if len(sys.argv) > 1 else "admin@practicape.pe"
db = SessionLocal()
u = db.query(models.User).filter_by(email=email).first()
if not u:
    u = models.User(email=email, name="Admin", role="admin")
    db.add(u)
else:
    u.role = "admin"
db.commit()
print(f"Admin OK: {u.email} (id={u.id}) — login vía OTP en /#/auth")
db.close()
