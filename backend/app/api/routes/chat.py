import json
import queue
import threading

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import AuthenticatedPrincipal
from app.contracts.chat import ChatRequest, ChatResponse
from app.core.config import settings
from app.core.errors import CuraError
from app.core.request_controls import request_controls
from app.db.session import SessionLocal, get_db
from app.pipeline.observability import ProgressEmitter
from app.pipeline.service import ChatService
from app.providers.registry import get_registry

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ChatResponse:
    request_id = request.headers.get("X-Request-Id") or request.state.request_id
    request_controls.check_rate_limit(principal.subject_id)
    cached = request_controls.begin_idempotency(principal.subject_id, idempotency_key, payload)
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
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StreamingResponse:
    request_id = request.headers.get("X-Request-Id") or request.state.request_id
    request_controls.check_rate_limit(principal.subject_id)
    cached = request_controls.begin_idempotency(principal.subject_id, idempotency_key, payload)
    if cached:
        cached.meta.cache_hit = True

        def cached_events():
            yield _event("status", {"state": "started", "request_id": request_id, "streaming": settings.chat_streaming_mode})
            yield _event("progress", {"stage": "COMPLETE", "message_key": "complete", "family": "personal", "follow_up": False})
            yield _event("complete", cached.model_dump(mode="json"))
            yield _event("answer", cached.model_dump(mode="json"))

        return StreamingResponse(
            cached_events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    events_q: queue.Queue = queue.Queue()

    def on_progress(event) -> None:
        events_q.put(("progress", event.model_dump(mode="json")))

    def on_preview(preview) -> None:
        events_q.put(("preview", preview.model_dump(mode="json")))

    def on_experience_block(block) -> None:
        events_q.put(("experience_block", block.model_dump(mode="json")))

    def worker() -> None:
        session = SessionLocal()
        try:
            emitter = ProgressEmitter(
                callback=on_progress,
                preview_callback=on_preview,
                experience_callback=on_experience_block,
            )
            response = ChatService(session, get_registry()).chat(
                principal, payload, request_id, progress=emitter
            )
            request_controls.idempotency_store(
                principal.subject_id, idempotency_key, payload, response
            )
            events_q.put(("complete", response.model_dump(mode="json")))
        except CuraError as exc:
            events_q.put(("error", {"code": exc.code, "message": exc.message}))
        except Exception:
            events_q.put(("error", {"code": "INTERNAL_ERROR", "message": "Something went wrong. Please try again."}))
        finally:
            session.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def events():
        yield _event("status", {"state": "started", "request_id": request_id, "streaming": settings.chat_streaming_mode})
        timeout = max(float(settings.request_timeout_seconds) + 10.0, 30.0)
        while True:
            try:
                kind, payload_data = events_q.get(timeout=timeout)
            except queue.Empty:
                yield _event("error", {"code": "TIMEOUT", "message": "The request timed out. Please try again."})
                break
            if kind == "progress":
                yield _event("progress", payload_data)
            elif kind == "preview":
                yield _event("preview", payload_data)
            elif kind == "experience_block":
                yield _event("experience_block", payload_data)
            elif kind == "complete":
                yield _event("complete", payload_data)
                yield _event("answer", payload_data)
                break
            elif kind == "error":
                yield _event("error", payload_data)
                break

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _event(name: str, payload: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


compat_router = APIRouter()


@compat_router.post("/cura/chat", response_model=ChatResponse)
def cura_chat(
    payload: ChatRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ChatResponse:
    return chat(payload, request, principal, db, idempotency_key)


@compat_router.post("/cura/chat/stream")
def cura_chat_stream(
    payload: ChatRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StreamingResponse:
    return chat_stream(payload, request, principal, idempotency_key)
