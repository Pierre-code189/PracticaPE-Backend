"""Recolector web sin API key para ofertas de Piura.

Fuentes:
- DuckDuckGo HTML (metabuscador, robots.txt permite el rastreo) como fuente principal.
- Computrabajo Perú (portal local) como complemento con datos de empresa/ubicación.

Las dos devuelven borradores (nunca se publican solos) y ante cualquier fallo de
red devuelven []: no se inventan ofertas.
"""
import html as html_mod
import random
import re
import time
import urllib.parse
import urllib.request

PIURA_KEYWORDS = ["piura", "castilla", "sullana", "talara", "pa\u00edta", "chulucanas",
                  "catacaos", "veintisseis", "tambogrande", "salitral", "morropon",
                  "la uni\u00f3n", "miguel checa", "bayovar", "la huaca"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# Pausa mínima entre peticiones a la misma fuente (cortesía + evitar bloqueos).
_LAST_HIT: dict[str, float] = {}
_PAUSE = 2.0


def _fetch(url: str, pause_key: str = "") -> str:
    """Descarga con UA de navegador y pausa entre peticiones."""
    if pause_key:
        wait = _PAUSE - (time.time() - _LAST_HIT.get(pause_key, 0.0))
        if wait > 0:
            time.sleep(wait)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "es-PE,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8", "ignore")
    finally:
        if pause_key:
            _LAST_HIT[pause_key] = time.time()
    return body


def _clean(txt: str) -> str:
    return html_mod.unescape(re.sub(r"<[^>]+>", "", txt or "")).strip()


def _ddg_results(query: str, max_results: int = 10) -> list[dict]:
    """DuckDuckGo HTML: resultados con URL real en uddg=."""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        html = _fetch(url, "ddg")
    except Exception:
        return []
    out = []
    for m in re.finditer(
            r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html, flags=re.S):
        href, title = m.group(1), _clean(m.group(2))
        real = href
        qm = re.search(r"[?&]uddg=([^&]+)", href)
        if qm:
            real = urllib.parse.unquote(qm.group(1))
        if "duckduckgo.com" in real or not real.startswith("http"):
            continue
        # snippet: el primer result__snippet posterior al enlace
        tail = html[m.end():m.end() + 2500]
        sm = re.search(r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', tail, flags=re.S)
        snippet = _clean(sm.group(1)) if sm else ""
        out.append({"url": real, "title": title, "snippet": snippet[:800]})
        if len(out) >= max_results:
            break
    return out


def _computrabajo_results(query: str, max_results: int = 10) -> list[dict]:
    """Computrabajo Perú: listado de ofertas (titulo, empresa, url)."""
    slug = re.sub(r"[^a-z0-9\u00ed\u00f3\u00e1\u00f1]+", "-", (query or "").lower()).strip("-")
    url = f"https://pe.computrabajo.com/trabajo-de-{slug}-en-piura"
    try:
        html = _fetch(url, "computrabajo")
    except Exception:
        return []
    out = []
    for m in re.finditer(r"<article[^>]*class=\"[^\"]*box_offer[^\"]*\"[^>]*>(.*?)</article>",
                         html, flags=re.S):
        block = m.group(1)
        am = re.search(r'<a[^>]*class="[^"]*js-o-link[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                       block, flags=re.S)
        if not am:
            continue
        href = am.group(1).split("#")[0]
        if href.startswith("/"):
            href = "https://pe.computrabajo.com" + href
        title = _clean(am.group(2))
        cm = re.search(r"<p[^>]*>\s*<a[^>]*>(.*?)</a>", block, flags=re.S)
        company = _clean(cm.group(1)) if cm else ""
        snippet = _clean(block)
        out.append({"url": href, "title": title, "snippet": snippet[:800], "company": company})
        if len(out) >= max_results:
            break
    return out


def _to_drafts(raw: list[dict], max_results: int) -> list[dict]:
    from .social_importer import parse_social_text
    drafts, seen = [], set()
    for r in raw:
        hay = (r["title"] + " " + r.get("snippet", "") + " " + r["url"]).lower()
        if not any(k in hay for k in PIURA_KEYWORDS):
            continue
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        d = parse_social_text(f"{r['title']}\n{r.get('snippet', '')}", r["url"])
        d["source"] = "web"
        d["title"] = r["title"][:180] or d["title"]
        drafts.append(d)
        if len(drafts) >= max_results:
            break
    return drafts


def collect_ddg(query: str = "practicante Piura", max_results: int = 10) -> list[dict]:
    return _to_drafts(_ddg_results(query, max_results * 2), max_results)


def collect_computrabajo(query: str = "practicante", max_results: int = 10) -> list[dict]:
    return _to_drafts(_computrabajo_results(query, max_results * 2), max_results)


def collect_search(query: str = "practicante Piura", max_results: int = 10) -> list[dict]:
    """Recolecta de ambas fuentes, deduplicando por URL."""
    merged: dict[str, dict] = {}
    for r in _ddg_results(query, max_results * 2) + _computrabajo_results(query, max_results * 2):
        merged.setdefault(r["url"], r)
    return _to_drafts(list(merged.values()), max_results)


def collect_bing(query: str = "practicante Piura", max_results: int = 10) -> list[dict]:
    """Alias histórico: Bing dejó de devolver resultados orgánicos; se usa DDG."""
    return collect_ddg(query, max_results)
