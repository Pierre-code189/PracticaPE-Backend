from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from .core.database import init_db
from .routers import auth, jobs, social, collect, admin, profiles

init_db()

app = FastAPI(title="PracticaPE", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, jobs.router, social.router, collect.router, admin.router, profiles.router):
    app.include_router(r)


@app.get("/health")
def health():
    return {"ok": True, "service": "PracticaPE"}


FRONT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(FRONT):
    app.mount("/static", StaticFiles(directory=os.path.join(FRONT, "static")), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(FRONT, "index.html"))
