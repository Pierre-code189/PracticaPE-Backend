"""Seed demo data: admin, 2 businesses, 2 candidates, companies, jobs, applications."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.database import SessionLocal, init_db
from app import models

init_db()
db = SessionLocal()

def user(email, name, role):
    u = db.query(models.User).filter_by(email=email).first()
    if not u:
        u = models.User(email=email, name=name, role=role)
        db.add(u); db.flush()
    return u

admin = user("admin@practicape.pe", "Admin", "admin")
b1 = user("negocio@demo.pe", "Demo Market", "business")
b2 = user("cafe@demo.pe", "Café Centro", "business")
c1 = user("ana@demo.pe", "Ana Torres", "candidate")
c2 = user("luis@demo.pe", "Luis Vega", "candidate")

comp1 = db.query(models.Company).filter_by(user_id=b1.id).first() or models.Company(user_id=b1.id)
for k, v in dict(name="Demo Market SAC", sector="Comercial", district="Piura", city="Piura",
                 lat=-5.1948, lng=-80.6308, phone="999888777", email="contacto@demomarket.pe",
                 description="Minimarket en el centro de Piura.", ruc="20123456789").items():
    setattr(comp1, k, v)
db.add(comp1)
comp2 = db.query(models.Company).filter_by(user_id=b2.id).first() or models.Company(user_id=b2.id)
for k, v in dict(name="Café Centro", sector="Restauración", district="Castilla", city="Piura",
                 lat=-5.188, lng=-80.64, phone="988777666", email="hola@cafecentro.pe",
                 description="Cafetería y panadería artesanal.", ruc="20987654321").items():
    setattr(comp2, k, v)
db.add(comp2)

for u, head, skills in [(c1, "Estudiante de Administración", "Excel,Ventas,Atención al cliente"),
                        (c2, "Estudiante de Sistemas", "Python,SQL,Soporte")]:
    p = db.query(models.CandidateProfile).filter_by(user_id=u.id).first() or models.CandidateProfile(user_id=u.id)
    p.headline, p.skills = head, skills
    db.add(p)

JOBS = [
    ("Cajero/a part-time", "presencial", "Piura", "S/ 600", comp1),
    ("Vendedor/a tienda", "presencial", "Castilla", "S/ 800 + comisiones", comp1),
    ("Barista", "presencial", "Castilla", "S/ 700", comp2),
    ("Soporte remoto practicante", "remoto", "Piura", "S/ 900", comp1),
    ("Ayudante de cocina (borrador)", "presencial", "Sullana", "S/ 650", comp2),
]
for i, (title, mod, dist, sal, comp) in enumerate(JOBS):
    if db.query(models.Job).filter_by(title=title).first():
        continue
    db.add(models.Job(company_id=comp.id, title=title, modality=mod, district=dist, city="Piura",
                      salary=sal, description=f"{title} — PracticaPE demo. Distrito {dist}.",
                      status="draft" if i == len(JOBS) - 1 else "published",
                      source="seed", lat=-5.19 + i * 0.01, lng=-80.63))
db.commit()
print("Seed OK: admin@practicape.pe / negocio@demo.pe / ana@demo.pe")
db.close()
