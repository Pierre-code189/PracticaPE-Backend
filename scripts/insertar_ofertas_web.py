"""Insertar ofertas reales halladas por busqueda como borradores (status=draft).
Patron de la casa: mismo que scripts/run_collector.py, con source='web'.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.database import SessionLocal, init_db
from app import models
from app.services.social_importer import parse_social_text

OFFERS = [
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-en-piura-B122D8DE3FED484261373E686DCF3405",
        "title": "Practicante — Estación de Servicios San José S.A.C. (Piura)",
        "district": "Piura",
        "modality": "presencial",
        "body": (
            "Practicante — Estación de Servicios San José S.A.C. (Piura)\n"
            "Empresa piurana con más de 30 años en el sector hidrocarburos (estaciones de servicio, "
            "tiendas de conveniencia, alquiler de vehículos y venta de neumáticos).\n"
            "Requisitos: egresado de Ingeniería Industrial, Administración o carreras afines; movilidad propia.\n"
            "Funciones: apoyar en gestión y organización de documentación del área, registrar y actualizar "
            "información de operaciones, elaborar reportes y cuadros de control, y brindar soporte administrativo.\n"
            "Modalidad: presencial, tiempo completo, convenio de prácticas. S/. a convenir.\n"
            "Publicado en Computrabajo (Piura) hace 14 horas."
        ),
    },
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-de-mantenimiento-fabrica-en-paita-B20C99E9B26E6D2D61373E686DCF3405",
        "title": "Practicante de Mantenimiento Fábrica — AgroAurora (Paita, Piura)",
        "district": "Paita",
        "modality": "presencial",
        "body": (
            "Practicante de Mantenimiento Fábrica — AgroAurora (Paita, Piura)\n"
            "Requisitos: egresado y/o bachiller en Ingeniería Mecánica, Eléctrica o afines; experiencia mínima "
            "de 3 meses en prácticas preprofesionales; Excel intermedio/avanzado y manejo de SAP.\n"
            "Funciones: apoyar al planner de mantenimiento en planes anuales de parada de planta y de operación, "
            "elaborar planes de mantenimiento de paradas cortas, registrar horas-hombre, controlar consumos de "
            "repuestos y lubricantes, y participar en análisis de fallas (ACR).\n"
            "Beneficios: movilidad gratuita, convenio de prácticas profesionales y seguro particular de salud.\n"
            "Modalidad: presencial, tiempo completo. S/. a convenir.\n"
            "Publicado en Computrabajo (Paita) hace 14 horas."
        ),
    },
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-de-comunicacion-y-responsabilidad-social-en-paita-D2D14029675FCD2F61373E686DCF3405",
        "title": "Practicante de Comunicación y Responsabilidad Social — AgroAurora (Paita, Piura)",
        "district": "Paita",
        "modality": "presencial",
        "body": (
            "Practicante de Comunicación y Responsabilidad Social — AgroAurora (Paita, Piura)\n"
            "Requisitos: bachiller o egresado de Ciencias de la Comunicación, Comunicación Social, Diseño Gráfico "
            "o afines; redacción y manejo de cámara profesional; diseño gráfico y edición de video a nivel "
            "intermedio (Canva, CapCut, Illustrator, Premiere); Office intermedio.\n"
            "Funciones: producción de piezas gráficas y audiovisuales, coberturas fotográficas, soporte a programas "
            "de responsabilidad social y a la atención de la comunidad, y apoyo en eventos internos y externos.\n"
            "Beneficios: movilidad gratuita, convenio de prácticas profesionales y seguro particular de salud.\n"
            "Modalidad: presencial, tiempo completo. S/. a convenir.\n"
            "Publicado en Computrabajo (Paita) ayer."
        ),
    },
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-profecional-de-contabilidad-en-piura-D2AA8BC4289B59A261373E686DCF3405",
        "title": "Practicante Profesional de Contabilidad — Empresa del sector (Piura)",
        "district": "Piura",
        "modality": "presencial",
        "body": (
            "Practicante Profesional de Contabilidad — Empresa del sector (Piura)\n"
            "Requisitos: egresado(a) o bachiller de Contabilidad; Excel intermedio o avanzado; proactivo, "
            "organizado y con disposición de aprender. Edad entre 24 y 30 años.\n"
            "Funciones: registro y control de información contable, organización de bases de datos y reportes en "
            "Excel, revisión y clasificación de documentos contables, y elaboración de cuadros de control.\n"
            "Se ofrece: aprendizaje y desarrollo profesional, experiencia práctica, acompañamiento y buen clima laboral.\n"
            "Modalidad: presencial, tiempo completo, convenio de prácticas. S/. a convenir.\n"
            "Publicado en Computrabajo (Piura) ayer."
        ),
    },
    {
        "url": "https://pe.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-practicante-profesional-de-negocios-sullana-en-sullana-2121E55AE2A7450B61373E686DCF3405",
        "title": "Practicante Profesional de Negocios Sullana — CAJA TRUJILLO (Sullana, Piura)",
        "district": "Sullana",
        "modality": "presencial",
        "body": (
            "Practicante Profesional de Negocios Sullana — CAJA TRUJILLO (Sullana, Piura)\n"
            "Institución microfinanciera con más de 41 años de trayectoria, certificación Great Place to Work "
            "2024-2025 y calificación B+ de Moody's Local.\n"
            "Reto: promocionar y concretar la venta de productos, servicios, seguros y canales en la zona de "
            "influencia de la tienda asignada.\n"
            "Requisitos: egresado de Economía, Administración, Contabilidad, Ingeniería o afines; Office básico; "
            "experiencia en labor de campo o ventas.\n"
            "Se ofrece: capacitación especializada en microfinanzas, subvención económica y beneficios de ley.\n"
            "Modalidad: presencial, tiempo completo, convenio de prácticas. S/. a convenir.\n"
            "Publicado en Computrabajo (Sullana) ayer."
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
