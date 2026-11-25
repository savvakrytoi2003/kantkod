class KantKodError(Exception):
    """Base class for all application errors."""


class SourceApiError(KantKodError):
    """Source portal API is unavailable or returned an unusable response."""


class VacancyNotFoundError(KantKodError):
    """Requested vacancy does not exist in the database."""


class SyncInProgressError(KantKodError):
    """Another synchronization is already running."""


class AiClientError(KantKodError):
    """AI provider request failed after all retries."""


class AiContextLengthError(AiClientError):
    """AI provider rejected the request because the context is too large."""


class AiResponseInvalidError(KantKodError):
    """AI response does not satisfy the expected schema."""


class AiNotConfiguredError(KantKodError):
    """AI provider is disabled or its credentials are missing."""


class ReportGenerationError(KantKodError):
    """Report could not be generated or persisted."""


class InvalidSourcePayloadError(KantKodError):
    """Local JSON payload does not match the source API format."""


class InvalidResumeError(KantKodError):
    """Resume payload is empty or unusable."""
