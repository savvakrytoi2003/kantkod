import logging
import uuid
from typing import Any

from app.config.settings import Settings
from app.domain.entities.vacancy import SyncCounters, VacancyCandidate
from app.domain.errors import SourceApiError
from app.domain.services.content_hasher import ContentHasher
from app.domain.services.vacancy_normalizer import VacancyNormalizer
from app.infrastructure.api.trudvsem_client import TrudvsemClient
from app.infrastructure.cache.redis_vacancy_cache import RedisVacancyCache
from app.infrastructure.database.clock import utcnow
from app.infrastructure.database.repositories.sync_run_repository import SyncRunRepository
from app.infrastructure.database.repositories.vacancy_repository import VacancyRepository
from app.schemas.api_response import SyncResultDTO

logger = logging.getLogger(__name__)


class SyncVacanciesUseCase:
    """Fetches vacancies from the source portal and synchronizes them with PostgreSQL."""

    def __init__(
        self,
        settings: Settings,
        client: TrudvsemClient,
        normalizer: VacancyNormalizer,
        hasher: ContentHasher,
        vacancy_repository: VacancyRepository,
        sync_run_repository: SyncRunRepository,
        cache: RedisVacancyCache,
    ) -> None:
        self._settings = settings
        self._client = client
        self._normalizer = normalizer
        self._hasher = hasher
        self._vacancies = vacancy_repository
        self._runs = sync_run_repository
        self._cache = cache

    async def prepare(self) -> uuid.UUID:
        run = await self._runs.start(status="pending")
        logger.info("sync run prepared", extra={"run_id": str(run.id)})
        return run.id

    async def execute(
        self,
        run_id: uuid.UUID | None = None,
        max_vacancies: int | None = None,
    ) -> SyncResultDTO:
        run = run_id
        if run is None:
            run = (await self._runs.start(status="running")).id
        else:
            await self._runs.finish(run, "running", 0, 0, 0, 0, 0)

        counters = SyncCounters()
        failed_pages = 0
        logger.info("sync started", extra={"run_id": str(run)})

        try:
            fetch_result = await self._client.fetch(
                max_vacancies=max_vacancies or self._settings.source_max_vacancies,
            )
            failed_pages = fetch_result.failed_pages
            counters.received = fetch_result.received_count
            logger.info(
                "vacancies received",
                extra={
                    "run_id": str(run),
                    "received": fetch_result.received_count,
                    "unique": len(fetch_result.items),
                    "pages": fetch_result.pages_fetched,
                    "failed_pages": fetch_result.failed_pages,
                },
            )

            for item in fetch_result.items:
                try:
                    await self._process_item(item, counters)
                except Exception as exc:
                    counters.failed += 1
                    logger.exception(
                        "vacancy processing failed",
                        extra={"run_id": str(run), "error": f"{type(exc).__name__}: {exc}"},
                    )

            status = "partial" if failed_pages or counters.failed else "success"
            error_message = None
            if failed_pages:
                error_message = f"{failed_pages} source page(s) failed"
            elif counters.failed:
                error_message = f"{counters.failed} vacancy(ies) failed to process"
        except SourceApiError as exc:
            logger.error("sync failed", extra={"run_id": str(run), "error": str(exc)})
            await self._runs.finish(
                run,
                "failed",
                counters.received,
                counters.created,
                counters.updated,
                counters.unchanged,
                counters.failed,
                str(exc),
            )
            raise
        await self._runs.finish(
            run,
            status,
            counters.received,
            counters.created,
            counters.updated,
            counters.unchanged,
            counters.failed,
            error_message,
        )
        logger.info(
            "sync finished",
            extra={
                "run_id": str(run),
                "status": status,
                "received": counters.received,
                "created_count": counters.created,
                "updated": counters.updated,
                "unchanged": counters.unchanged,
                "failed": counters.failed,
            },
        )
        return SyncResultDTO(
            run_id=run,
            status=status,
            received_count=counters.received,
            created_count=counters.created,
            updated_count=counters.updated,
            unchanged_count=counters.unchanged,
            failed_count=counters.failed,
            error_message=error_message,
        )

    async def _process_item(self, item: dict[str, Any], counters: SyncCounters) -> None:
        candidate = self._build_candidate(item)
        if candidate is None:
            counters.failed += 1
            logger.warning("vacancy skipped: invalid or missing identifier")
            return

        synced_at = utcnow()
        existing = await self._vacancies.get_by_external_id(candidate.external_id)
        if existing is None:
            await self._vacancies.create(candidate, synced_at)
            counters.created += 1
            await self._cache.invalidate_vacancy(candidate.external_id)
            return

        if existing.content_hash == candidate.content_hash:
            counters.unchanged += 1
            return

        await self._vacancies.update(existing.id, candidate, synced_at)
        counters.updated += 1
        await self._cache.invalidate_vacancy(candidate.external_id)

    def _build_candidate(self, item: dict[str, Any]) -> VacancyCandidate | None:
        normalized = self._normalizer.normalize(item)
        if normalized is None:
            return None
        return VacancyCandidate(
            normalized=normalized,
            raw=item,
            content_hash=self._hasher.hash(normalized),
        )
