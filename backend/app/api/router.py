from fastapi import APIRouter

from app.api.routes import auth, chat, consent, context, conversations, documents, feedback, health, me, voice

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(consent.router)
api_router.include_router(conversations.router)
api_router.include_router(documents.router)
api_router.include_router(feedback.router)
api_router.include_router(me.router)
api_router.include_router(voice.router)
api_router.include_router(context.router)
api_router.include_router(health.router)
