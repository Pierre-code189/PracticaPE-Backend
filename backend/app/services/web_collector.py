"""Bing web collector: searches Bing for Piura job listings, extracts
result URLs/titles, filters to Piura-related results, returns draft dicts.
No API key required. Network failures return [] (never fabricated jobs)."""
import base64
import re
import html as html_mod
import urllib.request
import urllib.parse

PIURA_KEYWORDS = ["piura", "castilla", "sullana", "talara", "pa\u00edta", "chulucanas",
                  "catacaos", "veintisseis", "tambogrande", "salitral", "morropon"]


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PracticaPE/1.0",
                                               "Accept-Language": "es-PE,es;q=0.9"})
    return urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")


def _decode_bing_url(href: str) -> str:
    """Bing ck/a redirect links carry the real URL base64-encoded in u=."""
    href = html_mod.unescape(href)
    if "bing.com/ck/a" in href:
        m = re.search(r"[?&]u=a1([A-Za-z0-9+/=_-]+)", href)
        if m:
            try:
                b64 = m.group(1)
                b64 += "=" * (-len(b64) % 4)
                real = base64.urlsafe_b64decode(b64).decode("utf-8", "ignore")
                if real.startswith("http"):
                    return real
            except Exception:
                pass
    return href


def _extract_results(html: str):
    results = []
    blocks = re.findall(r'<li class="b_algo".*?(?=<li class="b_algo"|</ol>)', html, flags=re.S)
    for block in blocks:
        m = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.S)
        if not m:
            m = re.search(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, flags=re.S)
        if not m:
            continue
        url = _decode_bing_url(m.group(1))
        title = html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if "bing.com" in url or "microsoft.com" in url or not url.startswith("http"):
            continue
        snippet = html_mod.unescape(re.sub(r"<[^>]+>", " ", block))
        results.append({"url": url, "title": title, "snippet": snippet[:800]})
    return results


def collect_bing(query: str = "empleos Piura", max_results: int = 10):
    q = urllib.parse.quote((query or "empleos Piura") + " Piura")
    url = f"https://www.bing.com/search?q={q}&count={max_results * 2}&cc=pe&setlang=es&mkt=es-PE"
    try:
        html = _fetch(url)
    except Exception:
        return []
    raw = _extract_results(html)
    from .social_importer import parse_social_text
    drafts, seen = [], set()
    for r in raw:
        hay = (r["title"] + " " + r["snippet"] + " " + r["url"]).lower()
        if not any(k in hay for k in PIURA_KEYWORDS):
            continue
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        d = parse_social_text(f"{r['title']}\n{r['snippet']}", r["url"])
        d["source"] = "web"
        d["title"] = r["title"][:180] or d["title"]
        drafts.append(d)
        if len(drafts) >= max_results:
            break
    return drafts
