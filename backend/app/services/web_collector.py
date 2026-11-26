"""Recolector web sin API key para ofertas de Piura.

Fuentes:
- DuckDuckGo HTML (metabuscador, robots.txt permite el rastreo) como fuente principal.
- Computrabajo Perú (portal local) como complemento con datos de empresa/ubicación.

Las dos devuelven borradores (nunca se publican solos) y ante cualquier fallo de
red devuelven []: no se inventan ofertas.
"""
import html as html_mod
import json
import random
import re
import time
import urllib.parse
import urllib.request

# ---------- Normalización de URL (clave de deduplicación) ----------
_TRACKING = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "gbraid", "wbraid", "mc_cid", "mc_eid", "ref", "ref_src",
}


def canonical_url(url: str | None) -> str:
    """Devuelve una URL comparable: sin fragmento, sin tracking y sin www.

    Se guarda esta forma en `source_url` para que dos portales que apuntan al
    mismo aviso con parámetros de campaña distintos no generen dos filas.
    """
    s = (url or "").strip()
    if not s:
        return ""
    s = s.split("#", 1)[0]
    try:
        p = urllib.parse.urlsplit(s)
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        query = [
            (k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
            if k.lower() not in _TRACKING
        ]
        path = p.path.rstrip("/") or "/"
        return urllib.parse.urlunsplit((
            p.scheme.lower(), host, path,
            urllib.parse.urlencode(query), "",
        ))
    except Exception:
        return s


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
    """Recolecta de todas las fuentes, deduplicando por URL."""
    merged: dict[str, dict] = {}
    for r in (_ddg_results(query, max_results * 2)
              + _computrabajo_results(query, max_results * 2)
              + _practicas_pe_results(max_results)
              + _gobpe_results(query, max_results)):
        merged.setdefault(r["url"], r)
    return _to_drafts(list(merged.values()), max_results)


def collect_bing(query: str = "practicante Piura", max_results: int = 10) -> list[dict]:
    """Alias histórico: Bing dejó de devolver resultados orgánicos; se usa DDG."""
    return collect_ddg(query, max_results)


# ---------- Fuentes adicionales (verificadas en el VPS, sin API key) ----------
PRACTICAS_PE_URL = "https://www.practicas.pe/pre-profesional-region-piura-20.html"
GOBPE_URL = "https://www.gob.pe/busquedas?term="


def _practicas_pe_results(max_results: int = 10) -> list[dict]:
    """Bolsa de prácticas de practicas.pe filtrada por la región Piura."""
    try:
        page = _fetch(PRACTICAS_PE_URL, "practicas_pe")
    except Exception:
        return []
    out = []
    for m in re.finditer(
            r'<a[^>]+href="(https://www\.practicas\.pe/oferta-convocatoria[^"]+\.html)"[^>]*>(.*?)</a>',
            page, flags=re.S):
        url, title = m.group(1), _clean(m.group(2))
        if not title:
            continue
        out.append({"url": url, "title": title, "snippet": title[:800]})
        if len(out) >= max_results:
            break
    return out


def _json_array_after(text: str, marker: str) -> list:
    """Lee el array JSON que sigue a un marcador, respetando comillas y escapes."""
    i = text.find(marker)
    if i < 0:
        return []
    i += len(marker)
    depth, in_str, esc = 0, False, False
    for j in range(i, len(text)):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[i:j + 1])
                        return value if isinstance(value, list) else []
                    except (ValueError, TypeError):
                        return []
    return []


def _gobpe_results(query: str = "practicante piura", max_results: int = 10) -> list[dict]:
    """Convocatorias del Estado peruano. Solo del año en curso: las demás caducaron."""
    try:
        page = _fetch(GOBPE_URL + urllib.parse.quote(query or "practicante piura"), "gobpe")
    except Exception:
        return []
    year = str(time.localtime().tm_year)
    out = []
    for item in _json_array_after(page, '"results":['):
        title = _clean(item.get("name_with_parent", ""))
        pub = item.get("publication") or ""
        if year not in pub:
            continue
        hm = re.search(r'href="([^"]+)"', item.get("url") or "")
        if not hm:
            continue
        href = hm.group(1).replace("\\/", "/")
        if href.startswith("/"):
            href = "https://www.gob.pe" + href
        out.append({"url": href, "title": title, "snippet": title[:800], "publication": pub})
        if len(out) >= max_results:
            break
    return out


def collect_practicas_pe(query: str = "", max_results: int = 10) -> list[dict]:
    return _to_drafts(_practicas_pe_results(max_results), max_results)


def collect_gobpe(query: str = "practicante piura", max_results: int = 10) -> list[dict]:
    return _to_drafts(_gobpe_results(query, max_results), max_results)
