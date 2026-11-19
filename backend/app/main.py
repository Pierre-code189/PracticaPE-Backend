import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.database import init_db
from .routers import admin, auth, collect, jobs, profiles, social

init_db()

app = FastAPI(title=settings.app_name, version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

SECURE_PREFIXES = ("/me", "/admin", "/business", "/jobs", "/social", "/collect")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if request.url.path.startswith(SECURE_PREFIXES):
        response.headers["Cache-Control"] = "no-store"
    return response


for r in (auth.router, jobs.router, social.router, collect.router, admin.router, profiles.router):
    app.include_router(r)


@app.get("/health")
def health():
    return {"ok": True, "service": settings.app_name}


FRONT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data")
if os.path.isdir(FRONT):
    app.mount("/static", StaticFiles(directory=os.path.join(FRONT, "static")), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(FRONT, "index.html"))
if os.path.isdir(os.path.join(DATA, "uploads")):
    app.mount("/uploads", StaticFiles(directory=os.path.join(DATA, "uploads")), name="uploads")
