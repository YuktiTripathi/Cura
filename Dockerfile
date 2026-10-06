# Cura API image (production readiness plan, 5.1). Build from the repo root:
#   docker build -t cura-api .
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

WORKDIR /srv/cura/backend

COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-deps -r requirements.lock

COPY integrations /srv/cura/integrations
COPY backend /srv/cura/backend

RUN useradd --system --uid 10001 cura \
    && mkdir -p /srv/cura/backend/data \
    && chown -R cura /srv/cura/backend/data
USER cura

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=4).status == 200 else 1)"

# Several workers, no --reload. Size WEB_CONCURRENCY from the load test.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-4} --proxy-headers --no-server-header"]
