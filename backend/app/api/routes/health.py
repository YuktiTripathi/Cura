from fastapi import APIRouter

from app.core.config import settings
from integrations.supershyft.db import probe_supershyft

router = APIRouter()


@router.get("/health")
def api_health():
    ss = probe_supershyft()
    return {
        "status": "ok",
        "llm_enabled": settings.enable_llm,
        "jev_enabled": settings.jev_enabled,
        "supershyft_db_configured": ss.configured,
        "supershyft": ss.public_dict(),
        "cura_db": "sqlite" if settings.cura_database_is_sqlite() else "external",
        "redis_configured": bool(settings.redis_url),
    }
