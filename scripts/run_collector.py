"""Run Bing collector -> drafts. Usage: python scripts/run_collector.py [query]"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.database import SessionLocal, init_db
from app import models
from app.services import web_collector

init_db()
query = sys.argv[1] if len(sys.argv) > 1 else "empleos Piura"
drafts = web_collector.collect_bing(query)
db = SessionLocal()
created = 0
for d in drafts:
    if d.get("source_url") and db.query(models.Job).filter_by(source_url=d["source_url"]).first():
        continue
    db.add(models.Job(company_id=None, **d))
    created += 1
db.commit()
print(f"Collector: found={len(drafts)} created_drafts={created}")
db.close()
