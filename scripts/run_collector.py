"""Recolector de ofertas reales de Piura -> revisión (nunca publica solo).

Uso:
    python scripts/run_collector.py [--limit N] [--query "practicante"]

Fuentes: Computrabajo Perú, practicas.pe (región Piura), DuckDuckGo HTML
(metabuscador) y convocatorias del Estado (gob.pe). Deduplica por URL y guarda
`source='web'`, `status='pending'`: la moderación la hace una persona desde la cola.
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
    # Las fuentes directas van primero: un aviso suyo gana sobre la copia que
    # pueda devolver el metabuscador.
    lotes = [
        web_collector.collect_computrabajo(query, limit * 2),
        web_collector.collect_practicas_pe(query, limit * 2),
        web_collector.collect_ddg(query, limit * 2),
        web_collector.collect_gobpe(query, limit * 2),
    ]
    # Intercalado (round-robin): con un límite bajo, un portal muy prolífico no
    # debe dejar fuera a los demás.
    for i in range(max((len(lote) for lote in lotes), default=0)):
        for lote in lotes:
            if i >= len(lote):
                continue
            d = lote[i]
            # Un fragmento #no cambia el aviso pero sí rompe la dedupe.
            url = (d.get("source_url") or "").split("#")[0].strip()
            if not url or url in seen:
                continue
            seen.add(url)
            d["source_url"] = url
            merged.append(d)
            if len(merged) >= limit:
                return merged
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
