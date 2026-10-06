import logging
import time
import uuid
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.chat import compat_router as chat_compat_router
from app.api.routes.voice import compat_router as voice_compat_router
from app.core.config import settings
from app.core.errors import CuraError, cura_error_handler, http_error_handler
from app.core.invariants import assert_production_config, assert_safe_auth_health_pairing
from app.core.logging import configure_logging
from app.db.session import init_db
from fastapi import HTTPException

configure_logging()
assert_safe_auth_health_pairing(settings)
assert_production_config(settings)
init_db()
try:
    from app.documents.jobs import drain_pending_document_jobs

    drain_pending_document_jobs()
except Exception:
    logging.getLogger("cura").warning("pending_document_job_drain_failed")

app = FastAPI(title="Cura", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
app.include_router(chat_compat_router)
app.include_router(voice_compat_router)
app.add_exception_handler(CuraError, cura_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)


@app.exception_handler(Exception)
async def unhandled_error(_request: Request, exc: Exception):
    if isinstance(exc, CuraError):
        return await cura_error_handler(_request, exc)
    logging.getLogger("cura").exception("unhandled")
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Something went wrong. Please try again.",
                "details": {},
            }
        },
    )


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    started = time.perf_counter()
    request.state.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    try:
        response = await call_next(request)
    except Exception:
        logging.getLogger("cura").exception(
            "request_failed request_id=%s method=%s path=%s",
            request.state.request_id,
            request.method,
            request.url.path,
        )
        raise
    response.headers["X-Request-Id"] = request.state.request_id
    logging.getLogger("cura").info(
        "request request_id=%s method=%s path=%s status=%s latency_ms=%s",
        request.state.request_id,
        request.method,
        request.url.path,
        response.status_code,
        int((time.perf_counter() - started) * 1000),
    )
    return response


@app.get("/health")
def health():
    from integrations.supershyft.db import probe_supershyft

    ss = probe_supershyft()
    return {
        "status": "ok",
        "supershyft_db_configured": ss.configured,
        "supershyft": ss.public_dict(),
        "cura_db": "sqlite" if settings.cura_database_is_sqlite() else "external",
    }


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    from integrations.supershyft.db import probe_supershyft

    ss = probe_supershyft()
    body = {
        "status": "ok",
        "health_provider": settings.health_provider,
        "llm_enabled": settings.enable_llm,
        "jev_enabled": settings.jev_enabled,
        "supershyft_db_configured": ss.configured,
        "supershyft": ss.public_dict(),
        "cura_db": "sqlite" if settings.cura_database_is_sqlite() else "external",
    }
    return body
