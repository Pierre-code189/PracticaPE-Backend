"""PrácticaPE — aplicación FastAPI.

Capas: core -> models -> services -> routers -> main.
Reglas transversales:
  - Nada de secretos embebidos (config).
  - Nada de emails en claro en BD (models/security).
  - Visibilidad por rol: borradores y perfiles ajenos no se filtran.
  - Cabeceras de seguridad y `no-store` en rutas privadas.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

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


FRONTEND = BASE_DIR + "/../frontend"


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/")
def index():
    return {"app": settings.app_name, "docs": "/docs"}


try:
    app.mount("/static", StaticFiles(directory=FRONTEND + "/static"), name="static")
except RuntimeError:  # pragma: no cover
    pass
