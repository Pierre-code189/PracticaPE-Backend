"""Insertar ofertas reales halladas por busqueda web el 2026-11-19 como borradores.
Patron de la casa: mismo que scripts/run_collector.py, con source='web', status='draft'.
Fuentes: Computrabajo / Indeed (Piura). Max 5 envios por dia. Endpoint real: no existe
/api/intake (404); se usa insercion directa de borradores.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.database import SessionLocal, init_db
from app import models
from app.services.social_importer import parse_social_text

OFFERS = [
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-de-marketing-par-time-en-castilla-047944D37FEF5D6A61373E686DCF3405",
        "title": "Practicante de Márketing — LA ESTACION MAR Y BRASAS (Castilla, Piura)",
        "district": "Castilla",
        "modality": "presencial",
        "body": (
            "Practicante de Márketing — LA ESTACION MAR Y BRASAS (Castilla, Piura)\n"
            "Restaurante piurano especializado en comida criolla y marina. Tiempo parcial, "
            "presencial, contrato por necesidades del mercado. Remuneración a convenir.\n"
            "Requisitos: estudiante de últimos ciclos, egresado(a) o técnico(a) en Marketing, "
            "Publicidad, Comunicaciones o afines; marketing digital y gestión de redes sociales; "
            "manejo de Facebook, Instagram y TikTok; creación de contenido audiovisual; Canva y "
            "edición de video.\n"
            "Funciones: gestionar y mantener activas las redes sociales, crear publicaciones, "
            "historias, reels y videos; proponer campañas y estrategias de marketing; apoyar en "
            "la difusión de ofertas y novedades; evaluar la interacción en redes.\n"
            "Publicado en Computrabajo (Castilla) hace 21 horas."
        ),
    },
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-de-control-de-gestion-e-indicadores-rubro-financiero-en-piura-1A6E145F6BC9204561373E686DCF3405",
        "title": "Practicante de Control de Gestión e Indicadores — COOPAC Santa Isabel (Piura)",
        "district": "Piura",
        "modality": "presencial",
        "body": (
            "Practicante de Control de Gestión e Indicadores — COOPAC Santa Isabel (Piura)\n"
            "Cooperativa financiera. Tiempo completo, presencial, contrato por inicio o incremento "
            "de actividad. Remuneración a convenir.\n"
            "Misión: apoyar a la Dirección y Jefatura de la Universidad Corporativa en la recopilación, "
            "registro, depuración y análisis de la data formativa, consolidando y reportando los "
            "indicadores de gestión de UCSI.\n"
            "Funciones: consolidar y depurar la data de capacitación y desempeño de los productos "
            "(Impulsa Mujer, El Tigre, Microcrédito, Impulsa Pyme) y de Habilidades Blandas; registrar "
            "y actualizar indicadores en el Sistema Integrado UCSI; elaborar reportes y tableros de "
            "seguimiento (cobertura, asistencia, horas de formación, Kirkpatrick N1 y N2); validar la "
            "calidad y trazabilidad de la información; apoyar en logística, viáticos y archivo del área.\n"
            "Publicado en Computrabajo (Piura) hace 21 horas."
        ),
    },
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-de-control-de-costos-en-paita-3E273055E0F717E361373E686DCF3405",
        "title": "Practicante de Control de Costos — DP World Logistics S.R.L (Paita, Piura)",
        "district": "Paita",
        "modality": "presencial",
        "body": (
            "Practicante de Control de Costos — DP World Logistics S.R.L (Paita, Piura)\n"
            "Empresa transnacional líder en facilitación del comercio y cadena logística. Convenio de "
            "Prácticas, tiempo completo, presencial. Remuneración a convenir.\n"
            "Requisitos: certificado de egreso en Negocios Internacionales, Ingeniería Industrial, "
            "Administración, Contabilidad o afines; Office nivel intermedio; inglés intermedio; "
            "deseable Power BI intermedio; experiencia mínima de 3 meses en finanzas y operaciones.\n"
            "Funciones: soporte en recepción y revisión de documentación; validación de conceptos "
            "facturados según tarifas, control de duplicidades; detección y reporte de servicios "
            "adicionales y sobrecostos; gestión de reclamos a proveedores y seguimiento de Notas de "
            "Crédito; revisión de Estados de Cuenta y saldos de Órdenes de Compra; revisión de Actas "
            "de Conformidad en sistema Máximo.\n"
            "Beneficios: todo lo establecido por ley y capacitación constante.\n"
            "Publicado en Computrabajo (Paita) ayer."
        ),
    },
    {
        "url": "https://pe.indeed.com/viewjob?jk=552c8a5f5e5089f7",
        "title": "Practicante Profesional de Canal Contact Center – Piura — Integratel (Piura)",
        "district": "Piura",
        "modality": "presencial",
        "body": (
            "Practicante Profesional de Canal Contact Center – Piura — Integratel (Piura)\n"
            "S/. 2.200 mensuales. Modalidad prácticas, empleo presencial.\n"
            "Misión: brindar soporte al seguimiento y control de la operación del canal Contact Center, "
            "monitoreando indicadores de desempeño, calidad y satisfacción del cliente, y coordinando "
            "con el proveedor para impulsar mejoras en la atención.\n"
            "Funciones: monitorear KPIs de atención, solución y satisfacción; analizar diferencias de "
            "desempeño entre asesores; seguimiento diario al proveedor; identificar incidencias y "
            "reiteraciones de llamadas; proponer mejoras en protocolos y procesos; muestreos de calidad "
            "de llamadas; escalar incidencias y participar en reuniones de calibración.\n"
            "Requisitos: estudiante de últimos ciclos o egresado de Administración, Ingeniería Industrial "
            "o afines; Excel y PowerPoint avanzados; SQL indispensable; análisis de datos e indicadores; "
            "negociación y comunicación asertiva.\n"
            "Beneficios: seguro FOLA y acompañamiento en gestión de operaciones y experiencia del cliente.\n"
            "Publicado en Indeed (Piura)."
        ),
    },
    {
        "url": "https://pe.indeed.com/viewjob?jk=be8b86d921ac08f3",
        "title": "Practicante de Administración y RRHH — OADH S.A.C (Piura)",
        "district": "Piura",
        "modality": "remoto",
        "body": (
            "Practicante de Administración-rrhh, (técnico o Uni) — OADH S.A.C (Piura)\n"
            "Temporal, prácticas. Lugar de trabajo: remoto.\n"
            "Funciones: soporte en reclutamiento y selección de personal; publicación de ofertas y "
            "recepción de currículums; filtros curriculares y coordinación de entrevistas; actualización "
            "de la base de datos del personal; gestión de archivo físico y digital; apoyo en control de "
            "asistencia, permisos y documentación; reportes e indicadores administrativos y de RRHH; "
            "actividades de inducción, capacitación y bienestar.\n"
            "Requisitos: estudiante de últimos ciclos (8vo en adelante) de Administración, Recursos "
            "Humanos, Gestión del Talento Humano o afines; Office básico/intermedio (Excel y Word); "
            "conocimientos en reclutamiento y selección; organización, comunicación y proactividad.\n"
            "Publicado en Indeed (Piura)."
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
    print("OK:", d["title"], "|", d["district"], d["modality"], "| salary:", d["salary"])
db.commit()
print(f"created={created} skipped={skipped}")
db.close()
