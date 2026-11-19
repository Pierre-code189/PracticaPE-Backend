"""Recolector de ofertas reales de Piura -> borradores (nunca publica solo).

Uso:
    python scripts/run_collector.py [query] [--limit N]

Fuentes: Computrabajo Peru (ofertas individuales) y DuckDuckGo HTML (cobertura).
Deduplica por URL contra la base. Las ofertas quedan como borrador para revision.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.database import SessionLocal, init_db  # noqa: E402
from app import models  # noqa: E402
from app.services import web_collector  # noqa: E402

DEFAULT_QUERIES = ["practicante", "practicas", "empleo piura", "trabajo piura", "part-time piura"]


def collect(query: str, limit: int) -> list[dict]:
    """Une ambas fuentes y deduplica por URL."""
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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    limit = 10
    if "--limit" in sys.argv:
        i = sys.argv.index("--limit")
        if i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
    queries = [args[0]] if args else DEFAULT_QUERIES

    init_db()
    db = SessionLocal()
    created = total = 0
    try:
        for q in queries:
            drafts = collect(q, limit)
            total += len(drafts)
            for d in drafts:
                url = d.get("source_url") or ""
                if url and db.query(models.Job).filter_by(source_url=url).first():
                    continue
                db.add(models.Job(company_id=None, **d))
                created += 1
            db.commit()
            print(f"  {q}: {len(drafts)} halladas")
            time.sleep(1.0)
    finally:
        db.close()
    print(f"Collector: found={total} created_drafts={created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
