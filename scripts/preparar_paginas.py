"""Prepara las pantallas de Stitch para servirlas como fragmentos de la SPA.

Fuente de verdad: .stitch/designs/*.html  ->  frontend/static/pages/*.html
Idempotente: se puede volver a correr tras una re-descarga.

Qué hace con cada pantalla:
  1. Extrae <body> y envuelve su contenido en <div class="pp-screen" data-page="{slug}">.
  2. Quita el <header> propio de Stitch (el cromo lo monta la SPA) y anota los
     destinos de navegación en data-nav para cablearlos desde el router.
  3. Elimina el <script id="tailwind-config"> (los tokens viven en tailwind-config.js).
  4. Conserva los <script> propios de la pantalla para inventarioar los controles.
  5. Añade el token pp-screen al <body> de la SPA.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, ".stitch", "designs")
DST = os.path.join(ROOT, "frontend", "static", "pages")

# Nombre de fichero Stitch -> (slug de ruta, titulo)
PAGES = {
    "home": ("home", "PrácticaPE · Prácticas y empleo en Piura"),
    "ofertas": ("ofertas", "Ofertas en Piura · PrácticaPE"),
    "oferta-detalle": ("oferta-detalle", "Detalle de oferta · PrácticaPE"),
    "auth-otp": ("auth", "Acceso · PrácticaPE"),
    "perfil-candidato": ("perfil-candidato", "Mi perfil · PrácticaPE"),
    "panel-empresa": ("panel-empresa", "Panel de empresa · PrácticaPE"),
    "directorio-empresas": ("empresas", "Directorio de empresas · PrácticaPE"),
    "mapa-ofertas": ("mapa", "Mapa de ofertas · PrácticaPE"),
    "mis-postulaciones": ("postulaciones", "Mis postulaciones · PrácticaPE"),
    "panel-administracion": ("panel-admin", "Panel de administración · PrácticaPE"),
    "notificaciones": ("notificaciones", "Notificaciones · PrácticaPE"),
    "perfil-publico": ("perfil-publico", "Perfil de candidata · PrácticaPE"),
    "publicar-oferta": ("publicar-oferta", "Publicar oferta · PrácticaPE"),
    "contacto": ("contacto", "Contacto y soporte · PrácticaPE"),
    "politica-privacidad": ("privacidad", "Política de privacidad · PrácticaPE"),
    "terminos-servicio": ("terminos", "Términos y condiciones · PrácticaPE"),
    "libro-de-reclamaciones": ("libro-de-reclamaciones", "Libro de reclamaciones · PrácticaPE"),
    "como-funciona": ("guias", "Guía de prácticas · PrácticaPE"),
}

NAV = {
    "ofertas": "#/ofertas",
    "mapa": "#/mapa",
    "empresas": "#/empresas",
    "directorio-de-empresas": "#/empresas",
    "mis-postulaciones": "#/postulaciones",
    "postulaciones": "#/postulaciones",
    "login": "#/auth",
    "iniciar-sesion": "#/auth",
    "registro": "#/auth",
    "publicar-oferta": "#/panel-empresa",
    "panel-empresa": "#/panel-empresa",
    "perfil-candidata": "#/perfil",
    "perfil-de-empresa": "#/empresas",
    "cola-de-moderacion": "#/panel-admin/cola",
    "leads-de-contacto": "#/panel-admin/leads",
    "usuarios": "#/panel-admin",
    "configuracion": "#/perfil",
    "contacto": "#/contacto",
    "contacto-empresas": "#/contacto",
    "soporte-piura": "#/contacto",
    "guias-laborales": "#/guias",
    "convenios-universitarios": "#/convenios",
    "instituciones": "#/empresas",
    "terminos-y-condiciones": "#/terminos",
    "terminos-condiciones": "#/terminos",
    "aviso-privacidad": "#/privacidad",
    "aviso-de-privacidad": "#/privacidad",
    "politica-de-privacidad": "#/privacidad",
    "libro-de-reclamaciones": "#/libro-de-reclamaciones",
    "libro-reclamaciones": "#/libro-de-reclamaciones",
    "postulantes": "#/panel-empresa/postulantes",
    "resumen": "#/panel-empresa",
    "oferta": "#/ofertas",
}


def nav_href(dest: str) -> str:
    return NAV.get(dest, "#/" + dest)


def extract_body(html: str) -> str:
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    return m.group(1) if m else ""


def strip_header(body: str) -> str:
    """Quita el <header> de Stitch; la SPA monta el suyo."""
    return re.sub(r"<header\b.*?</header>", "", body, count=1, flags=re.S)


def strip_tailwind_config(body: str) -> str:
    return re.sub(r'<script id="tailwind-config">.*?</script>', "", body, count=1, flags=re.S)


def wire_nav(body: str) -> str:
    def repl(m):
        tag, dest = m.group(0), m.group(1)
        if 'href="#"' not in tag and 'data-nav' in tag:
            return tag
        tag = tag.replace('href="#"', 'href="%s"' % nav_href(dest), 1)
        if "data-nav" not in tag:
            tag = tag.replace("<a ", '<a data-nav ', 1)
        return tag

    return re.sub(r'<a\b[^>]*data-path="([^"]+)"[^>]*>', repl, body)


def collect_scripts(body: str) -> list:
    return re.findall(r"<script(?![^>]*id=\"tailwind-config\")[^>]*>.*?</script>", body, re.S)


def main() -> int:
    os.makedirs(DST, exist_ok=True)
    resumen = []
    for fname, (slug, title) in PAGES.items():
        src = os.path.join(SRC, fname + ".html")
        if not os.path.isfile(src):
            resumen.append((fname, "FALTA", 0))
            continue
        html = open(src, encoding="utf-8").read()
        body = extract_body(html)
        body = strip_tailwind_config(body)
        body = strip_header(body)
        body = wire_nav(body)
        scripts = collect_scripts(body)
        # Los scripts quedan dentro del fragmento: la SPA los ejecuta al montar la página.
        out = (
            '<div class="pp-screen" data-page="%s" data-title="%s">\n'
            "%s\n"
            "</div>\n" % (slug, title, body.strip())
        )
        dst = os.path.join(DST, slug + ".html")
        open(dst, "w", encoding="utf-8").write(out)
        resumen.append((fname, "ok", len(out)))
    for name, estado, tam in resumen:
        print("%-24s %-6s %6d bytes" % (name, estado, tam))
    faltan = [n for n, e, _ in resumen if e != "ok"]
    if faltan:
        print("FALTAN: " + ", ".join(faltan))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
