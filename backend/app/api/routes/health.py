from fastapi import APIRouter

from app.core.config import settings
from integrations.supershyft.db import probe_supershyft, sanitized_db_target

router = APIRouter()


@router.get("/health")
def api_health():
    ss = probe_supershyft()
    body = {
        "status": "ok",
        "env": settings.app_env,
        "health_provider": settings.health_provider,
        "llm_enabled": settings.enable_llm,
        "llm_provider": settings.resolved_llm_provider() if settings.enable_llm else "off",
        "jev_enabled": settings.jev_enabled,
        "voice_enabled": settings.voice_enabled,
        "stt_provider": settings.stt_provider,
        "supershyft_db_configured": ss.configured,
        "supershyft": ss.public_dict(),
        "cura_db": "sqlite" if settings.cura_database_is_sqlite() else "external",
        "redis_configured": bool(settings.redis_url),
    }
    if settings.is_development and settings.supershyft_database_url:
        body["supershyft_target"] = sanitized_db_target(settings.supershyft_database_url)
    return body
