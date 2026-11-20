#!/usr/bin/env bash
# PrácticaPE — arranque del contenedor.
# Hace el seed solo si se pide (SEED_ON_START=1) y levanta uvicorn.
set -euo pipefail

cd /app/backend

if [ "${SEED_ON_START:-0}" = "1" ]; then
  echo "[entrypoint] seed inicial"
  python scripts/seed.py --publish >/dev/null 2>&1 || echo "[entrypoint] el seed falló; se continúa"
fi

echo "[entrypoint] uvicorn en :${PORT:-8000}"
exec python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips '*'
