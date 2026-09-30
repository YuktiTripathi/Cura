from fastapi import APIRouter, Depends, Request, Response

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.core.config import settings
from app.core.errors import UnauthorizedError

router = APIRouter()


@router.post("/auth/session")
def create_session(
    request: Request,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(get_principal),
) -> dict:
    header = request.headers.get("Authorization", "")
    token = header.split(" ", 1)[1].strip() if header.lower().startswith("bearer ") else ""
    if not token:
        raise UnauthorizedError("Bearer authentication required to create a session")
    response.set_cookie(
        key="cura_session",
        value=token,
        httponly=True,
        secure=not settings.is_development,
        samesite="lax",
        max_age=60 * 60 * 8,
        path="/",
    )
    return {"status": "ok", "user_id": principal.subject_id}
