"""PrácticaPE — aplicación FastAPI.

Capas: core -> models -> services -> routers -> main.
Reglas transversales:
  - Nada de secretos embebidos (config).
  - Nada de emails en claro en BD (models/security).
  - Visibilidad por rol: borradores y perfiles ajenos no se filtran.
  - Cabeceras de seguridad y `no-store` en rutas privadas.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pathlib import Path

from .core.config import BASE_DIR, settings
from .core.database import init_db
from .routers import admin, auth, business, companies, jobs, me, profile, public


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)

PRIVATE_PREFIX = ("/me", "/business", "/admin")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(self), camera=(), microphone=()",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    for k, v in SECURITY_HEADERS.items():
        response.headers[k] = v
    if path.startswith(PRIVATE_PREFIX) or path.startswith("/auth"):
        response.headers["Cache-Control"] = "no-store"
    elif path.startswith("/static/") or path == "/" or path == "":
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # No se filtra el detalle de la excepción al cliente.
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(companies.router)
app.include_router(profile.router)
app.include_router(business.router)
app.include_router(me.router)
app.include_router(admin.router)
app.include_router(public.router)


FRONTEND = Path(settings.frontend_dir).resolve()
IS_SPA = not (FRONTEND / "static").is_dir()


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/")
def index():
    f = FRONTEND / "index.html"
    if not f.is_file():
        raise HTTPException(status_code=404, detail="Frontend no construido (npm run build)")
    return FileResponse(f)


if (FRONTEND / "static").is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND / "static")), name="static")

# Build de React: los assets reales se sirven del disco y cualquier otra ruta
# (p. ej. /ofertas) devuelve index.html para que el router del cliente decida.
# Declarado al final, después de los routers de API, para no robarles peticiones.
if IS_SPA:
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path and full_path != "assets":
            candidato = FRONTEND / full_path
            try:
                if candidato.is_file() and FRONTEND in candidato.resolve().parents:
                    return FileResponse(candidato)
            except OSError:
                pass
        f = FRONTEND / "index.html"
        if not f.is_file():
            raise HTTPException(status_code=404, detail="Frontend no construido (npm run build)")
        return FileResponse(f)
