"""Insertar ofertas reales halladas por busqueda web (2026-11-15) como borradores.
Patron de la casa: mismo que scripts/run_collector.py / insertar_ofertas_web.py,
con source='web', status='draft' y dedup por source_url.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.database import SessionLocal, init_db
from app import models
from app.services.social_importer import parse_social_text

OFFERS = [
    {
        "url": "https://pe.indeed.com/viewjob?jk=3434bcd272ffa3db",
        "title": "Practicante de Administración — GRUPO JAVISAC (Castilla, Piura)",
        "district": "Castilla",
        "modality": "presencial",
        "body": (
            "Practicante de Administración — GRUPO JAVISAC (Castilla, Piura)\n"
            "GRUPO JAVISAC, empresa del rubro metalmecánico, busca un(a) Practicante de Administración "
            "para apoyar las actividades administrativas de su sede en Piura.\n"
            "Requisitos: estudiante de últimos ciclos o egresado(a) de Administración o carreras afines; "
            "deseable experiencia en actividades administrativas o prácticas preprofesionales; Excel y Word "
            "básico; conocimientos de gestión documentaria y registros administrativos.\n"
            "Funciones: revisar, organizar y archivar documentos administrativos; registrar y actualizar "
            "información en formatos y controles internos; elaborar reportes y cuadros de control en Excel; "
            "apoyar en el registro de egresos de caja y revisión de sustentos; coordinar con las demás áreas.\n"
            "Horario: lunes a viernes 8:00-17:45 y sábados 8:00-13:00. Lugar: Urb. San Antonio, Mz. A, "
            "Lote 3, Castilla – Piura. Presencial, tiempo completo.\n"
            "Publicado en Indeed (Piura)."
        ),
    },
    {
        "url": "https://pe.indeed.com/viewjob?jk=0b873e9f4d7f242d",
        "title": "Practicante de Sistemas para desarrollo web y automatizaciones — EccoConstruct (Piura)",
        "district": "Piura",
        "modality": "remoto",
        "body": (
            "Practicante de Sistemas para desarrollo web y automatizaciones — EccoConstruct (Piura)\n"
            "Apoyar en la construcción, optimización y mantenimiento del ecosistema digital: desarrollo de "
            "software y plataformas web, automatización de procesos, administración de hosting y SEO.\n"
            "Funciones: diseño, codificación y pruebas de soluciones tecnológicas; creación y mantenimiento "
            "de sitios web; configuración de flujos de trabajo e integraciones; administración básica de "
            "servidores, dominios, bases de datos y copias de seguridad; SEO técnico y de contenido.\n"
            "Requisitos: estudiante de últimos ciclos de Ingeniería de Sistemas, Computación, Informática, "
            "Desarrollo de Software o afines; no se requiere experiencia previa; conocimientos básicos de "
            "programación, HTML/CSS/JS y bases de datos.\n"
            "Condiciones: jornada de 36 horas semanales, turnos flexibles (mañana o tarde), programa de 930 "
            "horas de prácticas con certificación. Modalidad: remoto.\n"
            "Publicado en Indeed (Piura)."
        ),
    },
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-administrativoa-medio-turno-en-piura-A9D744083AA8AABC61373E686DCF3405",
        "title": "Practicante Administrativo(a) — BORISAAC E.I.R.L. (Piura)",
        "district": "Piura",
        "modality": "presencial",
        "body": (
            "Practicante Administrativo(a) – Medio Turno — BORISAAC E.I.R.L. (Piura)\n"
            "BORISAAC, distribuidor autorizado de SOLGAS (GLP), busca practicante para apoyar la gestión "
            "administrativa, comercial y operativa.\n"
            "Funciones: emisión y registro de comprobantes de pago electrónicos; control de créditos y cuentas "
            "por cobrar; registro de ventas y cobranzas diarias; seguimiento de pedidos de gas; control de "
            "inventarios de balones de GLP; reportes en Excel; archivo documental.\n"
            "Requisitos: estudiante de últimos ciclos o egresado de Administración, Ingeniería Industrial, "
            "Contabilidad o afines; Excel y Word intermedio; sistemas web administrativos; facturación "
            "electrónica y control de inventarios básicos.\n"
            "Modalidad: presencial, tiempo parcial (medio turno), contrato a plazo indeterminado.\n"
            "Publicado en Computrabajo (Piura)."
        ),
    },
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-de-sistemas-en-paita-FC64F645D453FB8561373E686DCF3405",
        "title": "Practicante de Sistemas — AgroAurora S.A.C. (Paita, Piura)",
        "district": "Paita",
        "modality": "presencial",
        "body": (
            "Practicante de Sistemas — AgroAurora S.A.C. (Paita, Piura)\n"
            "Requisitos: egresado o bachiller en Ingeniería de Sistemas, Electrónica, Mecatrónica o afines; "
            "6 meses de experiencia; conocimientos en ensamblaje de computadoras, soporte técnico a usuarios, "
            "sistemas operativos, mantenimiento de equipos de comunicación, redes y sistemas CCTV.\n"
            "Funciones: apoyar en la instalación de componentes de software y hardware; atención de incidentes "
            "de usuarios; realización de backups; verificación del funcionamiento de equipos; mantenimiento de "
            "equipos informáticos.\n"
            "Beneficios: movilidad gratuita, convenio de prácticas profesionales y seguro particular de salud. "
            "Presencial, tiempo completo.\n"
            "Publicado en Computrabajo (Paita)."
        ),
    },
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-de-edicion-de-video-contenido-para-redes-sociales-en-sullana-E0EAF8FDACD4B45D61373E686DCF3405",
        "title": "Practicante de Edición de Video — STC PERÚ (Sullana, Piura)",
        "district": "Sullana",
        "modality": "presencial",
        "body": (
            "Practicante de Edición de Video – Contenido para redes sociales — STC PERÚ / Servicio Técnico de "
            "Computadoras para las Naciones (Sullana, Piura)\n"
            "Funciones: editar videos cortos para TikTok, Facebook e Instagram Reels; apoyar en la grabación de "
            "contenido de productos y servicios; crear videos promocionales, demostrativos y educativos; "
            "agregar textos, subtítulos, transiciones, música y efectos; adaptar videos a los formatos de cada red.\n"
            "Requisitos: estudiante de Diseño Gráfico, Comunicación Audiovisual, Marketing, Diseño Digital o "
            "afines; conocimientos de edición de video; manejo de CapCut, Canva u otras herramientas.\n"
            "Modalidad: beca/prácticas (convenio de prácticas).\n"
            "Publicado en Computrabajo (Sullana)."
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
models.log_event(db, "web_submit", f"ofertas creadas={created} duplicadas={skipped}")
db.commit()
print(f"created={created} skipped={skipped}")
db.close()
