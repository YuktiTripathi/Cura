import json

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.contracts.chat import ChatRequest, ChatResponse
from app.db.session import get_db
from app.pipeline.service import ChatService
from app.providers.registry import get_registry
from app.core.request_controls import request_controls

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ChatResponse:
    request_id = request.headers.get("X-Request-Id") or request.state.request_id
    request_controls.check_rate_limit(principal.subject_id)
    cached = request_controls.idempotency_lookup(principal.subject_id, idempotency_key, payload)
    if cached:
        cached.meta.cache_hit = True
        return cached
    response = ChatService(db, get_registry()).chat(principal, payload, request_id)
    request_controls.idempotency_store(
        principal.subject_id, idempotency_key, payload, response
    )
    return response


@router.post("/chat/stream")
def chat_stream(
    payload: ChatRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StreamingResponse:
    request_id = request.headers.get("X-Request-Id") or request.state.request_id
    request_controls.check_rate_limit(principal.subject_id)
    cached = request_controls.idempotency_lookup(principal.subject_id, idempotency_key, payload)
    response = cached or ChatService(db, get_registry()).chat(principal, payload, request_id)
    if not cached:
        request_controls.idempotency_store(
            principal.subject_id, idempotency_key, payload, response
        )
    else:
        response.meta.cache_hit = True

    def events():
        yield _event("status", {"state": "started", "request_id": request_id})
        # Chunking keeps the API truly incremental even when a provider lacks native token streaming.
        words = response.answer.split(" ")
        for start in range(0, len(words), 12):
            yield _event("token", {"text": " ".join(words[start : start + 12]) + " "})
        yield _event("complete", response.model_dump(mode="json"))

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _event(name: str, payload: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
