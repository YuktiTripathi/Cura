from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class CuraError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ValidationAppError(CuraError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__("VALIDATION_ERROR", message, 400, details)


class UnauthorizedError(CuraError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__("UNAUTHORIZED", message, 401)


class ForbiddenError(CuraError):
    def __init__(self, message: str = "Not allowed"):
        super().__init__("FORBIDDEN", message, 403)


class NotFoundError(CuraError):
    def __init__(self, message: str = "Not found"):
        super().__init__("NOT_FOUND", message, 404)


class AmbiguousDataError(CuraError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__("AMBIGUOUS_DATA", message, 409, details)


class ProviderUnavailableError(CuraError):
    def __init__(self, message: str | None = None, *, reason: str | None = None):
        from app.core.copy import PERSONAL_DATA_UNAVAILABLE

        super().__init__("PROVIDER_UNAVAILABLE", message or PERSONAL_DATA_UNAVAILABLE, 503)
        self.reason = reason
        if reason:
            self.details = {"reason": reason}


class VoiceUnavailableError(CuraError):
    def __init__(self, message: str = "Voice input isn't configured yet. You can continue by typing your message."):
        super().__init__("VOICE_UNAVAILABLE", message, 503)


class VoiceValidationError(CuraError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__("VOICE_VALIDATION_ERROR", message, 400, details)


class DocumentValidationError(CuraError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__("DOCUMENT_VALIDATION_ERROR", message, 400, details)


class DocumentUploadError(CuraError):
    def __init__(self, message: str = "Upload failed. Please try again."):
        super().__init__("DOCUMENT_UPLOAD_FAILED", message, 500)


class LLMUnavailableError(CuraError):
    def __init__(self, message: str = "LLM unavailable"):
        super().__init__("LLM_UNAVAILABLE", message, 503)


class RateLimitedError(CuraError):
    def __init__(self, message: str = "Rate limited"):
        super().__init__("RATE_LIMITED", message, 429)


class InternalError(CuraError):
    def __init__(self, message: str = "Internal error"):
        super().__init__("INTERNAL_ERROR", message, 500)


async def cura_error_handler(_request: Request, exc: CuraError) -> JSONResponse:
    from app.core.copy import PERSONAL_DATA_UNAVAILABLE

    message = exc.message
    details = exc.details
    if isinstance(exc, ProviderUnavailableError):
        message = PERSONAL_DATA_UNAVAILABLE
        details = {}
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": message, "details": details}},
    )


async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    code = "INTERNAL_ERROR"
    if exc.status_code == 401:
        code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    elif exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 422:
        code = "VALIDATION_ERROR"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": str(exc.detail), "details": {}}},
    )
