import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.errors import (
    AiClientError,
    AiNotConfiguredError,
    AiResponseInvalidError,
    InvalidResumeError,
    InvalidSourcePayloadError,
    KantKodError,
    ReportGenerationError,
    SourceApiError,
    SyncInProgressError,
    VacancyNotFoundError,
)

logger = logging.getLogger(__name__)

_STATUS_MAP: tuple[tuple[type[Exception], int], ...] = (
    (VacancyNotFoundError, status.HTTP_404_NOT_FOUND),
    (SyncInProgressError, status.HTTP_409_CONFLICT),
    (SourceApiError, status.HTTP_502_BAD_GATEWAY),
    (AiClientError, status.HTTP_502_BAD_GATEWAY),
    (AiResponseInvalidError, status.HTTP_502_BAD_GATEWAY),
    (AiNotConfiguredError, status.HTTP_503_SERVICE_UNAVAILABLE),
    (InvalidSourcePayloadError, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (InvalidResumeError, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (ReportGenerationError, status.HTTP_500_INTERNAL_SERVER_ERROR),
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(KantKodError)
    async def handle_kantkod_error(_: Request, exc: KantKodError) -> JSONResponse:
        status_code = status.HTTP_400_BAD_REQUEST
        for error_type, mapped_status in _STATUS_MAP:
            if isinstance(exc, error_type):
                status_code = mapped_status
                break
        logger.warning("request failed", extra={"error": f"{type(exc).__name__}: {exc}"})
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})
