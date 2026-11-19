# ---------- Stage 1: build (instala dependencias en un venv aislado) ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY backend/requirements.txt ./
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements.txt

# ---------- Stage 2: runner (sin root, solo runtime + venv) ----------
FROM python:3.12-slim AS runner

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PRACTICAPE_DATA_DIR=/app/data \
    PRACTICAPE_UPLOAD_DIR=/app/data/uploads

RUN groupadd --system app \
 && useradd --system --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY backend ./backend
COPY frontend ./frontend
COPY scripts ./scripts

RUN mkdir -p /app/data/uploads \
 && chmod +x /app/scripts/entrypoint.sh \
 && chown -R app:app /app

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health', timeout=3).status==200 else 1)"]

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
