# PrácticaPE — Backend

API de **PrácticaPE**, la plataforma peruana de prácticas preprofesionales y primer empleo en Piura.
FastAPI + SQLite, con recolección automática de ofertas desde portales públicos y enlace al anuncio
original.

> El frontend React vive en el repo aparte **[PracticaPE-Frontend](https://github.com/Pierre-code189/PracticaPE-Frontend)**.
> Aquí solo está la API, los scripts de recolección y la base de datos.

## Qué hace

- **Ofertas**: listado público paginado, detalle, fuentes (`/jobs/sources`) y scraping de portales.
- **Empresas**: directorio público y fichas.
- **Postulaciones y auth**: registro/login por OTP por correo, roles (candidato, negocio, admin).
- **Administración** (API): cola de moderación de ofertas scrapeadas, usuarios, leads.
- **Mapa**: `lat`/`lng` por oferta y distritos normalizados.

## Puesta en marcha

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
export PRACTICAPE_DATA_DIR=/tmp/practicape-data
mkdir -p "$PRACTICAPE_DATA_DIR"
python backend/scripts/seed.py --publish        # datos de demostración aprobados
PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 8000
```

La API queda en `http://127.0.0.1:8000` (documentación interactiva en `/docs`).

### Variables

| Variable | Por defecto | Para qué |
|---|---|---|
| `PRACTICAPE_DATA_DIR` | `./data` | Base de datos, subidas, buzón OTP |
| `PRACTICAPE_DB` | `sqlite:///<DATA_DIR>/practicape.db` | Cadena SQLAlchemy |
| `PRACTICAPE_FRONTEND_DIR` | `../frontend-dist` | Build de React que sirve la API |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Enlaces absolutos en correos |
| `CORS_ORIGINS` | `http://localhost:8000,...` | Orígenes permitidos |
| `SECRET_KEY` | (aleatoria) | Firmado de JWT/OTP; **definirla en producción** |
| `OTP_DEV_CODE` | vacío | Con valor `1`, el código OTP es `123456` (solo desarrollo) |

## Frontend

El backend sirve el build estático si existe (`PRACTICAPE_FRONTEND_DIR`) y actúa como *SPA
fallback*: devuelve `index.html` a cualquier ruta que no sea un asset ni un endpoint de API.

```bash
git clone https://github.com/Pierre-code189/PracticaPE-Frontend.git
cd PracticaPE-Frontend/frontend-react && npm ci && npm run build   # sale en ../dist
PRACTICAPE_FRONTEND_DIR=../dist PYTHONPATH=backend uvicorn app.main:app --reload
```

En Docker: montar el build como volumen sobre `/app/frontend-dist`. Si el build no existe, `/`
responde **404 “Frontend no construido (npm run build)”** y la API sigue funcionando.

## Recolección de ofertas

```bash
python scripts/run_collector.py --limit 12     # entra en la cola de moderación
```

Fuentes (sin API key, todas verificadas desde el VPS):

| Fuente | Cómo entra |Estado|
|---|---|---|
| Computrabajo Perú | listado directo por aviso | activa |
| **practicas.pe** | listado directo de la región Piura | activa |
| DuckDuckGo HTML | metabuscador: descubre Indeed, LinkedIn y otros | activa |
| **gob.pe** | convocatorias del Estado en el buscador | activa solo para el año en curso |

Ante un fallo de red, una fuente devuelve `[]` y las demás siguen. Las fuentes se intercalan para
que un portal prolífico no desplace a los otros, y todo se deduplica por `source_url` **canónica**
(sin fragmento, sin parámetros de tracking, sin `www.`). La BD tiene un índice único parcial como
red de seguridad y un `flock` evita dos recolectores simultáneos.

Las ofertas entran como `pending`; se aprueban por la API
(`PATCH /admin/queue/{id}?action=approve`). Cada una conserva `source_url`, y su procedencia se
muestra en la web.

## Tests

```bash
.venv/bin/pip install pytest
.venv/bin/pytest backend/tests/ -q          # suite de API, seguridad y requisitos
scripts/e2e_api.py                          # E2E contra una instancia levantada
```

## Despliegue

El VPS lo corre como systemd (`practicape.service`), con Nginx como proxy inverso y TLS. Ver el
README del repositorio principal para el diagrama completo.

## Diseño

Los tokens de marca y las pantallas fuente están en `.stitch/` (`DESIGN.md` y `designs/*.html`);
el contrato pantalla↔endpoint está en `docs/CONTRATO.md`.
