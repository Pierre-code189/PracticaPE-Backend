"""Insertar ofertas reales halladas por busqueda web el 2026-11-18 como borradores.
Patron de la casa: mismo que scripts/run_collector.py, con source='web', status='draft'.
Fuentes: Computrabajo / Indeed (Piura). Max 5 envios por dia.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.database import SessionLocal, init_db
from app import models
from app.services.social_importer import parse_social_text

OFFERS = [
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-profesional-de-derecho-relaciones-laborales-en-paita-BA813C29161BCFCA61373E686DCF3405",
        "title": "Practicante Profesional de Derecho – Relaciones Laborales — AGROAURORA S.A.C. (Paita, Piura)",
        "district": "Paita",
        "modality": "presencial",
        "body": (
            "Practicante Profesional de Derecho – Relaciones Laborales — AGROAURORA S.A.C. (Paita, Piura)\n"
            "S/. 1.230,00 mensuales. Convenio de Prácticas. Tiempo completo.\n"
            "Se integra al equipo de Gestión Humana brindando soporte en los procesos y actividades del área de "
            "Relaciones Laborales.\n"
            "Funciones: seguimiento y control de documentación de inspecciones internas; soporte en medidas "
            "disciplinarias; atención y seguimiento de órdenes de inspección ante SUNAFIL; seguimiento de procesos "
            "de desvinculación laboral; seguimiento del programa de quejas, consultas y sugerencias de los "
            "trabajadores; organización y ejecución de eventos del área.\n"
            "Requisitos: egresado(a) de la carrera de Derecho; conocimientos básicos de procedimientos de Recursos "
            "Humanos; Excel intermedio.\n"
            "Competencias: adaptabilidad y flexibilidad, orientación a resultados y capacidad de aprendizaje.\n"
            "Publicado en Computrabajo (Paita) hace 22 horas."
        ),
    },
    {
        "url": "https://pe.indeed.com/viewjob?jk=2efab594acdd5525",
        "title": "Practicante Administrativo Comercial — CAAP / Centro de Ayuda Académica Profesional (Piura)",
        "district": "Piura",
        "modality": "presencial",
        "body": (
            "Practicante Administrativo Comercial — CAAP / Centro de Ayuda Académica Profesional (Piura)\n"
            "Convocatoria para Practicante Administrativo Comercial en Piura. Convenio por 3 meses, incorporación "
            "inmediata, modalidad presencial, 4 a 6 horas diarias, con flexibilidad horaria según disponibilidad "
            "académica.\n"
            "La empresa es especializada en proyectos de investigación académica (tesis, monografías, ensayos y "
            "artículos científicos), con 27 años de trayectoria y presencia en Bolivia, Chile, Ecuador y Perú.\n"
            "Requisitos: estudiantes de últimos ciclos, egresados o recién graduados de Administración o carreras "
            "afines; residir en Piura; proactividad y responsabilidad.\n"
            "Funciones: apoyo en procesos administrativos y comerciales; coordinación con clientes y asesores "
            "académicos; manejo del sistema administrativo interno; soporte en funciones contables y operativas.\n"
            "Beneficios: crecimiento profesional, capacitaciones constantes, apoyo documentario para validar horas "
            "de prácticas. WhatsApp: +51 943 876 292.\n"
            "Publicado en Indeed (Piura)."
        ),
    },
    {
        "url": "https://pe.indeed.com/viewjob?jk=315ae1c94453abdd",
        "title": "Practicante de Logística Primaria — cbc (Sullana, Piura)",
        "district": "Sullana",
        "modality": "presencial",
        "body": (
            "Practicante de Logística Primaria — cbc (Sullana, Piura)\n"
            "Tiempo completo. CBC es una compañía comercializadora de bebidas y alimentos con 137 años de "
            "experiencia y operaciones en Centroamérica, el Caribe y Sudamérica; trabaja con socios estratégicos "
            "Pepsico, Ambev y Beliv.\n"
            "Retos: gestionar y brindar soporte en los procesos y rutinas de Materia Prima, Centro de Distribución y "
            "Transporte Primario País; generar KPIs del área integrados en ERP (SAP); soporte en reuniones de rutina; "
            "analizar procesos y proponer proyectos de mejora continua; dar seguimiento PMO a los programas de "
            "excelencia del área.\n"
            "Requisitos: estudiante de últimos ciclos o egresado de Ingeniería Industrial, Administración y/o "
            "carreras afines; Office avanzado; PowerBi y SAP (deseable); disponibilidad inmediata para trabajar en "
            "Sullana.\n"
            "Publicado en Indeed (Sullana, Piura)."
        ),
    },
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-trainee-de-energia-en-la-huaca-5A2455689053FA9361373E686DCF3405",
        "title": "Trainee de Energía — AGROAURORA S.A.C. (La Huaca, Piura)",
        "district": "La Huaca",
        "modality": "presencial",
        "body": (
            "Trainee de Energía — AGROAURORA S.A.C. (La Huaca, Piura)\n"
            "Programa Trainee de Energía. Remuneración a convenir. Contrato por obra determinada o servicio "
            "específico. Tiempo completo.\n"
            "Objetivo: brindar soporte en la gestión, monitoreo y optimización de los sistemas energéticos de la "
            "organización, contribuyendo a la eficiencia operacional y al cumplimiento de los objetivos de "
            "sostenibilidad.\n"
            "Requisitos: titulado en Ingeniería Mecánica Eléctrica, Ingeniería de Energía, Ingeniería Electrónica, "
            "Ingeniería Mecatrónica o afines; conocimientos básicos en sistemas eléctricos, eficiencia energética o "
            "gestión de energía; manejo de Excel.\n"
            "Funciones: monitoreo y análisis de consumos energéticos; reportes e indicadores de desempeño energético; "
            "proyectos de eficiencia energética y sostenibilidad; seguimiento a equipos y sistemas de suministro y "
            "consumo de energía; identificación de oportunidades de ahorro.\n"
            "Beneficios: capacitación constante, mentoría especializada, participación en proyectos de alto impacto "
            "y línea de carrera.\n"
            "Publicado en Computrabajo (La Huaca, Piura) ayer. La empresa no solicita pagos para postular."
        ),
    },
]

init_db()
db = SessionLocal()
created, skipped = 0, 0
for o in OFFERS:
    if db.query(models.Job).filter_by(source_url=o["url"]).first():
        print("SKIP duplicado:", o["url"])
        skipped += 1
        continue
    d = parse_social_text(o["body"], o["url"])
    d["title"] = o["title"][:180]
    d["district"] = o["district"]
    d["modality"] = o["modality"]
    d["source"] = "web"
    d["status"] = "draft"
    db.add(models.Job(company_id=None, **d))
    created += 1
    print("OK:", d["title"], "|", d["district"], d["modality"])
db.commit()
print(f"created={created} skipped={skipped}")
db.close()
