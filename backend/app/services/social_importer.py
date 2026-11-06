import re
from ..core.config import settings

PIURA_COORDS = {"Piura": (-5.1948, -80.6308), "Castilla": (-5.188, -80.64),
                "Sullana": (-4.903, -80.683), "Talara": (-4.577, -81.271),
                "Paita": (-5.095, -81.103), "Chulucanas": (-5.09, -80.16),
                "Catacaos": (-5.266, -80.67), "Veintisseis de Octubre": (-5.18, -80.62)}


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


def parse_url(url: str) -> dict:
    """Best-effort: fetch URL text and parse. Falls back to URL-derived draft."""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PracticaPE/1.0"})
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return parse_social_text(text[:4000], url)
    except Exception:
        slug = url.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ")
        return parse_social_text(f"{slug}\nImportado desde {url}", url)
