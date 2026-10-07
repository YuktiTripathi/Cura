import asyncio
import json

from fastapi import APIRouter, Depends, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import AuthenticatedPrincipal
from app.contracts.chat import ChatRequest, ChatResponse, public_chat_response
from app.core.config import settings
from app.core.consent import require_consent
from app.core.errors import CuraError
from app.core.metrics import observe_chat
from app.core.request_controls import chat_capacity, request_controls
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
    require_consent(db, principal.subject_id)
    request_controls.check_rate_limit(principal.subject_id)
    request_controls.check_token_budget(principal.subject_id)
    cached = request_controls.begin_idempotency(principal.subject_id, idempotency_key, payload)
    if cached:
        cached.meta.cache_hit = True
        return _client_view(cached)
    chat_capacity.acquire()
    try:
        response = ChatService(db, get_registry()).chat(principal, payload, request_id)
    finally:
        chat_capacity.release()
    _record_usage(principal.subject_id, response)
    request_controls.idempotency_store(
        principal.subject_id, idempotency_key, payload, response
    )
    return _client_view(response)


def _record_usage(subject_id: str, response: ChatResponse) -> None:
    meta = response.meta
    observe_chat(meta)
    used = (meta.input_tokens or 0) + (meta.output_tokens or 0) + (meta.jev_input_tokens or 0) + (meta.jev_output_tokens or 0)
    request_controls.record_token_usage(subject_id, used)
    request_controls.record_spend(meta.estimated_cost_usd)


def _client_view(response: ChatResponse) -> ChatResponse:
    return public_chat_response(response) if settings.public_meta_enabled() else response


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StreamingResponse:
    """Server-sent events. The pipeline runs in one bounded worker-pool thread and its
    progress reaches the client through an asyncio queue, so a stream no longer holds an
    extra raw thread plus a pool thread blocked on a queue (readiness plan 5.3)."""
    request_id = request.headers.get("X-Request-Id") or request.state.request_id
    cached = await run_in_threadpool(_stream_prelude, principal, payload, idempotency_key)
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    if cached:

        async def cached_events():
            yield _event("status", {"state": "started", "request_id": request_id, "streaming": settings.chat_streaming_mode})
            yield _event("progress", {"stage": "COMPLETE", "message_key": "complete", "family": "personal", "follow_up": False})
            yield _event("complete", cached.model_dump(mode="json"))
            yield _event("answer", cached.model_dump(mode="json"))

        return StreamingResponse(cached_events(), media_type="text/event-stream", headers=headers)

    chat_capacity.acquire()
    loop = asyncio.get_running_loop()
    events_q: asyncio.Queue = asyncio.Queue()

    def put(kind: str, data: dict) -> None:
        loop.call_soon_threadsafe(events_q.put_nowait, (kind, data))

    def worker() -> None:
        session = SessionLocal()
        try:
            emitter = ProgressEmitter(
                callback=lambda event: put("progress", event.model_dump(mode="json")),
                preview_callback=lambda preview: put("preview", preview.model_dump(mode="json")),
                experience_callback=lambda block: put("experience_block", block.model_dump(mode="json")),
                token_callback=lambda text: put("token", {"text": text}),
            )
            response = ChatService(session, get_registry()).chat(
                principal, payload, request_id, progress=emitter
            )
            _record_usage(principal.subject_id, response)
            request_controls.idempotency_store(
                principal.subject_id, idempotency_key, payload, response
            )
            put("complete", _client_view(response).model_dump(mode="json"))
        except CuraError as exc:
            put("error", {"code": exc.code, "message": exc.message})
        except Exception:
            put("error", {"code": "INTERNAL_ERROR", "message": "Something went wrong. Please try again."})
        finally:
            session.close()
            chat_capacity.release()

    # Keep a reference so the task finishes (and releases capacity) even if the client leaves.
    task = asyncio.ensure_future(run_in_threadpool(worker))
    _RUNNING.add(task)
    task.add_done_callback(_RUNNING.discard)

    async def events():
        yield _event("status", {"state": "started", "request_id": request_id, "streaming": settings.chat_streaming_mode})
        timeout = max(float(settings.request_timeout_seconds) + 10.0, 30.0)
        while True:
            try:
                kind, payload_data = await asyncio.wait_for(events_q.get(), timeout=timeout)
            except asyncio.TimeoutError:
                yield _event("error", {"code": "TIMEOUT", "message": "The request timed out. Please try again."})
                break
            if kind in {"progress", "preview", "experience_block", "token"}:
                yield _event(kind, payload_data)
            elif kind == "complete":
                yield _event("complete", payload_data)
                yield _event("answer", payload_data)
                break
            elif kind == "error":
                yield _event("error", payload_data)
                break

    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)


_RUNNING: set[asyncio.Future] = set()


def _stream_prelude(principal: AuthenticatedPrincipal, payload: ChatRequest, idempotency_key: str | None):
    """Blocking checks (database, Redis) kept off the event loop."""
    consent_session = SessionLocal()
    try:
        require_consent(consent_session, principal.subject_id)
    finally:
        consent_session.close()
    request_controls.check_rate_limit(principal.subject_id)
    request_controls.check_token_budget(principal.subject_id)
    cached = request_controls.begin_idempotency(principal.subject_id, idempotency_key, payload)
    if cached:
        cached.meta.cache_hit = True
        return _client_view(cached)
    return None


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
async def cura_chat_stream(
    payload: ChatRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StreamingResponse:
    return await chat_stream(payload, request, principal, idempotency_key)
