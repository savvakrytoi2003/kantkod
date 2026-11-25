import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config.settings import Settings
from app.schemas.report import ReportDTO
from app.schemas.vacancy import VacancyDetailDTO

logger = logging.getLogger(__name__)


class RedisVacancyCache:
    """Redis-backed cache for vacancies and reports.

    Every operation degrades gracefully: when Redis is unavailable the application
    continues to work through PostgreSQL.
    """

    _VACANCY_PREFIX = "vacancy"
    _REPORT_KEY = "report:latest"

    def __init__(self, client: Redis, settings: Settings) -> None:
        self._client = client
        self._ttl = settings.cache_ttl_seconds

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except (RedisError, OSError):
            return False

    async def get_vacancy(self, external_id: str) -> VacancyDetailDTO | None:
        try:
            raw = await self._client.get(self._vacancy_key(external_id))
        except (RedisError, OSError) as exc:
            logger.warning("cache read failed", extra={"key": external_id, "error": str(exc)})
            return None
        if not raw:
            return None
        try:
            return VacancyDetailDTO.model_validate_json(raw)
        except ValueError:
            return None

    async def set_vacancy(self, external_id: str, detail: VacancyDetailDTO) -> None:
        try:
            await self._client.set(self._vacancy_key(external_id), detail.model_dump_json(), ex=self._ttl)
        except (RedisError, OSError) as exc:
            logger.warning("cache write failed", extra={"key": external_id, "error": str(exc)})

    async def invalidate_vacancy(self, external_id: str) -> None:
        try:
            await self._client.delete(self._vacancy_key(external_id))
        except (RedisError, OSError) as exc:
            logger.warning("cache invalidation failed", extra={"key": external_id, "error": str(exc)})

    async def get_report(self) -> ReportDTO | None:
        try:
            raw = await self._client.get(self._REPORT_KEY)
        except (RedisError, OSError) as exc:
            logger.warning("report cache read failed", extra={"error": str(exc)})
            return None
        if not raw:
            return None
        try:
            return ReportDTO.model_validate_json(raw)
        except ValueError:
            return None

    async def set_report(self, report: ReportDTO) -> None:
        try:
            await self._client.set(self._REPORT_KEY, report.model_dump_json(), ex=self._ttl * 12)
        except (RedisError, OSError) as exc:
            logger.warning("report cache write failed", extra={"error": str(exc)})

    async def invalidate_report(self) -> None:
        try:
            await self._client.delete(self._REPORT_KEY)
        except (RedisError, OSError) as exc:
            logger.warning("report cache invalidation failed", extra={"error": str(exc)})

    def _vacancy_key(self, external_id: str) -> str:
        return f"{self._VACANCY_PREFIX}:{external_id}"
