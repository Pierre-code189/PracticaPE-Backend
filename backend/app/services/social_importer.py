"""Importación de ofertas desde texto libre o URL.

La variante URL está protegida contra SSRF (PE06): solo http(s), sin IPs
privadas/loopback/enlace-local y con revalidación en cada redirección.
"""
import ipaddress
import re
import socket
import urllib.parse
import urllib.request

from ..core.config import settings

PIURA_COORDS = {"Piura": (-5.1948, -80.6308), "Castilla": (-5.188, -80.64),
                "Sullana": (-4.903, -80.683), "Talara": (-4.577, -81.271),
                "Paita": (-5.095, -81.103), "Chulucanas": (-5.09, -80.16),
                "Catacaos": (-5.266, -80.67), "Veintisseis de Octubre": (-5.18, -80.62)}

MAX_FETCH_BYTES = 1_000_000
FETCH_TIMEOUT = 10


class UnsafeTarget(ValueError):
    """El destino no puede leerse (esquema, IP o redirección no permitida)."""


def detect_district(text: str) -> str:
    t = (text or "").lower()
    for d in sorted(settings.piura_districts, key=len, reverse=True):
        if d.lower() in t:
            return d
    return "Piura"


def detect_modality(text: str) -> str:
    t = (text or "").lower()
    if "remoto" in t or "remote" in t or "virtual" in t:
        return "remoto"
    if "hibrido" in t or "híbrido" in t:
        return "hibrido"
    return "presencial"


def parse_social_text(text: str, source_url: str = "") -> dict:
    """Parse free text / social post into a job draft dict."""
    text = text or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = lines[0][:120] if lines else "Oferta importada"
    salary = ""
    m = re.search(r"S/\.?\s?[\d\.,]+(?:\s*[-–]\s*[\d\.,]+)?", text)
    if m:
        salary = m.group(0)
    coords = PIURA_COORDS.get(detect_district(text), PIURA_COORDS["Piura"])
    return {
        "title": title,
        "description": text[:4000],
        "modality": detect_modality(text),
        "district": detect_district(text),
        "city": "Piura",
        "lat": coords[0], "lng": coords[1],
        "salary": salary,
        "source": "social",
        "source_url": source_url or "",
        "status": "draft",
    }


# ── SSRF guard ───────────────────────────────────────────────────────────────
def _host_allowed(host: str) -> bool:
    if not host:
        return False
    low = host.lower()
    if low in ("localhost", "localhost.localdomain") or low.endswith(".local") or low.endswith(".internal"):
        return False
    try:
        infos = socket.getaddrinfo(low, None)
    except Exception:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def validate_url(url: str) -> str:
    url = (url or "").strip()
    if len(url) > 500:
        raise UnsafeTarget("URL demasiado larga")
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeTarget("Solo se permiten URLs http(s)")
    if parts.username or parts.password:
        raise UnsafeTarget("URL con credenciales no permitida")
    if not parts.hostname or not _host_allowed(parts.hostname):
        raise UnsafeTarget("Destino no permitido")
    return url


class _RedirectGuard(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_RedirectGuard)


def fetch_url_text(url: str) -> str:
    """Descarga el texto de una URL pública segura (máx. 1 MB)."""
    validate_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "PracticaPE/1.0",
                                               "Accept-Language": "es-PE,es;q=0.9"})
    with _opener.open(req, timeout=FETCH_TIMEOUT) as resp:
        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype and "text" not in ctype and "json" not in ctype:
            raise UnsafeTarget("Tipo de contenido no permitido")
        data = resp.read(MAX_FETCH_BYTES)
    return data.decode("utf-8", "ignore")


def parse_url(url: str) -> dict:
    """Descarga y parsea una URL. Si no se puede leer, deriva un borrador del slug."""
    try:
        html = fetch_url_text(validate_url(url))
    except UnsafeTarget:
        raise
    except Exception:
        slug = url.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ")
        return parse_social_text(f"{slug}\nImportado desde {url}", url)
    text = re.sub(r"<script[\s\S]*?</script>", " ", html)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return parse_social_text(text[:4000], url)
