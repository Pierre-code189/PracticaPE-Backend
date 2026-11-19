#!/usr/bin/env bash
# PracticaPE entrypoint: prepara la BD y arranca uvicorn en 0.0.0.0:$PORT.
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
BACKEND_DIR="${BACKEND_DIR:-$APP_DIR/backend}"
export PRACTICAPE_DATA_DIR="${PRACTICAPE_DATA_DIR:-$APP_DIR/data}"
export PRACTICAPE_UPLOAD_DIR="${PRACTICAPE_UPLOAD_DIR:-$PRACTICAPE_DATA_DIR/uploads}"
export PORT="${PORT:-8000}"

cd "$BACKEND_DIR"

echo "[entrypoint] init_db en $PRACTICAPE_DATA_DIR ..."
python - <<'PY'
from app.core.database import init_db

init_db()
print("[entrypoint] init_db OK")
PY

if [ "${SEED_ON_START:-0}" = "1" ]; then
  echo "[entrypoint] seed de demo (SEED_ON_START=1) ..."
  python "$APP_DIR/scripts/seed.py" || echo "[entrypoint] seed falló; se continúa igualmente"
fi

echo "[entrypoint] uvicorn 0.0.0.0:$PORT"
exec python -m uvicorn --app-dir "$BACKEND_DIR" app.main:app --host 0.0.0.0 --port "$PORT"
