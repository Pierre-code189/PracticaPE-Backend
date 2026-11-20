"""Datos de ejemplo de PrácticaPE (empresas, ofertas, candidatos).

Uso: python scripts/seed.py [--reset]
No publica nada de una: las ofertas nacen como borrador salvo --publish.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.security import email_alias, email_hash_of, encrypt_email  # noqa: E402
from app.models import (  # noqa: E402
    Application, CandidateProfile, Company, Job, Lead, Notification, ProfileItem, User,
)

EMPRESAS = [
    ("Café Centro Piura S.A.C.", "Hostelería y restauración", "Piura", "Sector Habitat, Piura", -5.1945, -80.6336, "959 441 203"),
    ("Agroindustrias del Chira", "Agroindustria", "Sullana", "Carretera Panamericana Norte km 955", -4.9080, -80.6830, "968 117 440"),
    ("Logística Talara S.A.", "Logística y transporte", "Talara", "Zona industrial, Talara", -4.5780, -81.2720, "976 224 881"),
    ("Clínica San Francisco Piura", "Salud", "Castilla", "Av. Guardia Civil 420", -5.2000, -80.6200, "958 221 334"),
    ("Distribuidora Paita Norte", "Comercio", "Paita", "Av. Panamericana 1230", -5.0800, -81.1100, "998 551 207"),
]

OFERTAS = [
    ("Café Centro Piura S.A.C.", "Asistente administrativo", "Administración", "presencial", "Piura", "S/ 1.200 - S/ 1.600", 2,
     "Apoyarás en la gestión de compras, proveedores y archivo documentario de la sede de Piura. Buscamos a alguien con manejo de Excel y buena redacción. Horario: lunes a sábado, 8:00 a 14:00."),
    ("Café Centro Piura S.A.C.", "Cajero(a) medio tiempo", "Atención al cliente", "presencial", "Piura", "S/ 930 - S/ 1.050", 3,
     "Atención en caja y apoyo en el servicio a mesa. Se valora experiencia previa en atención al público. Turnos rotativos de 5 horas."),
    ("Agroindustrias del Chira", "Auxiliar de laboratorio", "Agroindustria", "presencial", "Sullana", "S/ 1.500 - S/ 1.900", 2,
     "Control de calidad de muestras de mango y banano orgánico. Conocimientos de buenas prácticas de laboratorio. Incluye alimentación y movilidad."),
    ("Agroindustrias del Chira", "Operario de empaque", "Producción", "presencial", "Sullana", "S/ 1.100 - S/ 1.400", 6,
     "Selección y empaque de fruta para exportación. Se brinda capacitación. Horario de 6:00 a 14:00."),
    ("Logística Talara S.A.", "Auxiliar de almacén", "Logística", "presencial", "Talara", "S/ 1.250 - S/ 1.500", 2,
     "Recepción, ubicación y despacho de mercadería. Experiencia mínima de 6 meses en almacén. Disponibilidad de horario."),
    ("Logística Talara S.A.", "Practicante de comercio exterior", "Comercio internacional", "remoto", "Talara", "S/ 1.000 - S/ 1.200", 1,
     "Apoyo en la documentación de exportación y seguimiento de cargas. Modalidad híbrida: 3 días presencial, 2 remoto."),
    ("Clínica San Francisco Piura", "Practicante de enfermería", "Salud", "presencial", "Castilla", "S/ 1.100 - S/ 1.300", 4,
     "Apoyo en triaje, signos vitales y curaciones básicas. Se requiere estar cursando el último año de la carrera."),
    ("Clínica San Francisco Piura", "Recepcionista bilingüe", "Administración", "presencial", "Castilla", "S/ 1.000 - S/ 1.200", 1,
     "Recepción de pacientes, programación de citas y manejo de historias clínicas. Inglés intermedio."),
    ("Distribuidora Paita Norte", "Reponedor de almacén", "Comercio", "presencial", "Paita", "S/ 930 - S/ 1.050", 2,
     "Reposición de mercadería y control de vencimientos. Horario de 7:00 a 15:00."),
    ("Distribuidora Paita Norte", "Practicante de marketing digital", "Marketing", "remoto", "Paita", "S/ 800 - S/ 1.000", 1,
     "Gestión de redes sociales y campañas locales. Se valora creatividad y manejo de Canva o herramientas afines."),
]

CANDIDATOS = [
    ("Ana Lucía Torres Zapata", "ana.torres@unp.edu.pe", "Derecho", "Castilla", 5, 4,
     "Estudiante de Derecho con interés en redacción legal y atención al cliente."),
    ("José Miguel Ruiz Cisneros", "jose.ruiz@unp.edu.pe", "Administración", "Piura", 3, 2,
     "Con experiencia en caja y manejo de Excel intermedio."),
    ("María Fernanda Sullón Pacherres", "maria.sullon@unp.edu.pe", "Enfermería", "Sullana", 4, 3,
     "Prácticas de laboratorio y triaje, con vocación de servicio."),
    ("Diego Alonso Mendoza Albán", "diego.mendoza@unp.edu.pe", "Ingeniería Industrial", "Talara", 6, 5,
     "Experiencia en almacén y control de inventarios."),
    ("Valeria Campos Delgado", "valeria.campos@unp.edu.pe", "Comercio Internacional", "Paita", 2, 1,
     "Inglés intermedio y manejo de office."),
    ("Carlos Alberto Ipanaqué Morán", "carlos.ipanaque@unp.edu.pe", "Contabilidad", "Piura", 4, 2,
     "Apoyo en conciliaciones y archivo documentario."),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--publish", action="store_true")
    args = ap.parse_args()

    init_db()
    db = SessionLocal()
    try:
        if args.reset:
            db.query(Application).delete()
            db.query(ProfileItem).delete()
            db.query(Job).delete()
            db.query(Company).delete()
            db.query(CandidateProfile).delete()
            db.query(User).delete()
            db.commit()

        users = {}
        for i, (name, email, _car, _dis, _c, _t, _res) in enumerate(CANDIDATOS, start=1):
            h = email_hash_of(email)
            u = db.query(User).filter(User.email_hash == h).first()
            if not u:
                u = User(email=email_alias(0), email_hash=h, email_enc=encrypt_email(email),
                         name=name, role="candidate")
                db.add(u)
                db.flush()
                u.email = email_alias(u.id)
                db.add(CandidateProfile(user_id=u.id))
            db.add(Notification(user_id=u.id, type="info", title="Bienvenido a PrácticaPE",
                                body="Completa tu perfil para que las empresas te encuentren.",
                                link="#/perfil"))
            users[email] = u

        comps = {}
        for i, (name, sector, district, address, lat, lng, phone) in enumerate(EMPRESAS, start=1):
            email = "contacto%d@%s.pe" % (i, name.split()[0].lower())
            h = email_hash_of(email)
            u = db.query(User).filter(User.email_hash == h).first()
            if not u:
                u = User(email=email_alias(0), email_hash=h, email_enc=encrypt_email(email),
                         name=name, role="business")
                db.add(u)
                db.flush()
                u.email = email_alias(u.id)
            c = db.query(Company).filter(Company.user_id == u.id).first()
            if not c:
                c = Company(user_id=u.id, name=name, sector=sector, district=district,
                            city=district, address=address, lat=lat, lng=lng, phone=phone,
                            is_verified=(i <= 3), description="Empresa piurana con vacantes de práctica y primer empleo.")
                db.add(c)
                db.flush()
            comps[name] = c

        db.commit()

        for name, title, cat, mod, district, salary, positions, desc in OFERTAS:
            c = comps[name]
            exists = db.query(Job).filter(Job.company_id == c.id, Job.title == title).first()
            if exists:
                continue
            db.add(Job(
                company_id=c.id, title=title, description=desc, category=cat, modality=mod,
                district=district, city=district, lat=(c.lat or 0) + 0.002, lng=(c.lng or 0) + 0.002,
                salary=salary, positions=positions, status="published" if args.publish else "draft",
                source="seed",
            ))
        db.commit()

        for name, email, carrera, district, ciclo, sem, resumen in CANDIDATOS:
            u = users[email]
            p = db.query(CandidateProfile).filter(CandidateProfile.user_id == u.id).first()
            if p and not p.headline:
                p.headline = carrera
                p.summary = resumen
                p.district = district
                p.city = district
                p.skills = "Trabajo en equipo, Oficina, Comunicación"
                db.add(ProfileItem(profile_id=p.id, kind="education", title=carrera,
                                   org="Universidad Nacional de Piura", start="2023", end="2027",
                                   description="Ciclo %d · %d créditos" % (ciclo, sem)))
        db.commit()

        if args.publish:
            for name, email, _c, _d, _ci, _s, _r in CANDIDATOS:
                u = users[email]
                job = db.query(Job).filter(Job.status == "published").first()
                if job and not db.query(Application).filter(Application.job_id == job.id, Application.candidate_id == u.id).first():
                    db.add(Application(job_id=job.id, candidate_id=u.id, status="applied",
                                        message="Me interesa la vacante."))

        db.commit()
        db.add(Lead(name="Empresa interesada", email="empresa@example.com", phone="999 888 777",
                    message="Queremos publicar tres vacantes de práctica.", type="company"))
        db.commit()
        print("seed ok: %d candidatos, %d empresas, %d ofertas" % (
            db.query(User).filter(User.role == "candidate").count(),
            db.query(Company).count(),
            db.query(Job).count(),
        ))
    finally:
        db.close()


if __name__ == "__main__":
    main()
