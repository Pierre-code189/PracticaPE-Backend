"""Recolector de ofertas reales de Piura -> revisión (nunca publica solo).

Uso:
    python scripts/run_collector.py [--limit N] [--query "practicante"]

Fuentes: Computrabajo Perú (ofertas individuales) y DuckDuckGo HTML (cobertura).
Deduplica por URL contra la base. Todo queda como `pending` para que administración
lo apruebe o lo rechace desde la cola.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models import Job  # noqa: E402
from app.services import web_collector  # noqa: E402

DEFAULT_QUERIES = [
    "practicante", "practicas profesionales", "empleo piura", "trabajo piura",
    "part-time piura", "recien egresado piura",
]

QUERIES = os.getenv("COLLECTOR_QUERIES", "").split("|") if os.getenv("COLLECTOR_QUERIES") else DEFAULT_QUERIES


def collect(query: str, limit: int) -> list[dict]:
    seen, merged = set(), []
    for d in web_collector.collect_computrabajo(query, limit * 2) + web_collector.collect_ddg(query, limit * 2):
        url = d.get("source_url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        merged.append(d)
        if len(merged) >= limit:
            break
    return merged


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default=None, help="consulta única")
    ap.add_argument("--limit", type=int, default=10)
    ns = ap.parse_args()
    limit = ns.limit
    queries = [ns.query] if ns.query else [q for q in QUERIES if q.strip()]

    init_db()
    db = SessionLocal()
    created = total = 0
    try:
        for q in queries:
            drafts = collect(q, limit)
            total += len(drafts)
            for d in drafts:
                url = (d.get("source_url") or "")[:500]
                if url and db.query(Job).filter(Job.source_url == url).first():
                    continue
                db.add(Job(
                    company_id=None,
                    title=(d.get("title") or "Oferta encontrada")[:255],
                    description=(d.get("description") or "")[:4000],
                    modality=d.get("modality", "presencial"),
                    district=d.get("district", "Piura"),
                    city=d.get("city", "Piura"),
                    lat=d.get("lat"), lng=d.get("lng"),
                    salary=(d.get("salary") or "")[:100],
                    status="pending",
                    source="web",
                    source_url=url,
                ))
                created += 1
            db.commit()
            print("  %s: %d halladas" % (q, len(drafts)))
            time.sleep(1.0)
    finally:
        db.close()
    print("Collector: found=%d en_revision=%d" % (total, created))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
