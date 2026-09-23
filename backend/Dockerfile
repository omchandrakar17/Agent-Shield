# syntax=docker/dockerfile:1
# -----------------------------------------------------------------------------
# Stage 1: Build stage
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /build/wheels ".[gcp]"

# -----------------------------------------------------------------------------
# Stage 2: Final minimal rootless runtime
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    AGENTSHIELD_ENV=production \
    AGENTSHIELD_SEED_USERS=false \
    AGENTSHIELD_RUN_MIGRATIONS=false

RUN groupadd -g 10001 agentshield && \
    useradd -u 10001 -g agentshield -m -s /bin/bash agentshield && \
    mkdir -p /app/data && \
    chown -R agentshield:agentshield /app

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY --chown=agentshield:agentshield app/ /app/app/
COPY --chown=agentshield:agentshield alembic/ /app/alembic/
COPY --chown=agentshield:agentshield alembic.ini /app/alembic.ini

USER 10001

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\", \"8080\")}/health').read()" || exit 1

CMD ["sh", "-c", "if [ \"${AGENTSHIELD_RUN_MIGRATIONS}\" = \"true\" ]; then python -m alembic upgrade head; fi && uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2 --proxy-headers"]
