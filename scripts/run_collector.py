"""Recolector de ofertas reales de Piura -> revisión (nunca publica solo).

Uso:
    python scripts/run_collector.py [--limit N] [--query "practicante"]

Fuentes: Computrabajo Perú, practicas.pe (región Piura), DuckDuckGo HTML
(metabuscador) y convocatorias del Estado (gob.pe). Deduplica por URL y guarda
`source='web'`, `status='pending'`: la moderación la hace una persona desde la cola.
"""
import fcntl
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from sqlalchemy.exc import IntegrityError

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
            # clave canónica: sin fragmento, sin tracking, sin www, sin barra final
            url = web_collector.canonical_url(d.get("source_url") or "")
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

    # Solo una corrida a la vez: SQLite se bloquea si dos procesos escriben.
    # El índice único es la red de datos; este lock evita el error de base.
    data_dir = os.getenv("PRACTICAPE_DATA_DIR", "data")
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "collector.lock"), "a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Collector: otro recolector ya está corriendo; se omite esta corrida")
            return 0
        return _run(queries, limit)


def _run(queries, limit: int) -> int:
    init_db()
    db = SessionLocal()
    created = total = 0
    try:
        for q in queries:
            drafts = collect(q, limit)
            total += len(drafts)
            for d in drafts:
                url = web_collector.canonical_url(d.get("source_url") or "")[:500]
                if not url or db.query(Job).filter(Job.source_url == url).first():
                    continue
                titulo = (d.get("title") or "").strip().lower()
                if titulo and db.query(Job).filter(Job.title.ilike(titulo)).first():
                    # No bloquea: avisos distintos pueden compartir título.
                    print("  aviso: título ya visto con otra URL → %s" % titulo[:60])
                try:
                    # SAVEPOINT: si otro recolector insertó la misma URL entre la
                    # consulta y el add, el índice único lo rechaza sin perder
                    # el resto de la tanda.
                    with db.begin_nested():
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
                except IntegrityError:
                    continue
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
