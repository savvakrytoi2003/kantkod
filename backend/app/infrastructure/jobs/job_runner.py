import logging
import uuid

from dishka import AsyncContainer

from app.domain.use_cases.analyze_vacancies import AnalyzeVacanciesUseCase
from app.domain.use_cases.generate_report import GenerateReportUseCase
from app.domain.use_cases.sync_vacancies import SyncVacanciesUseCase

logger = logging.getLogger(__name__)


class JobRunner:
    """Runs long use cases outside of the HTTP request scope."""

    def __init__(self, container: AsyncContainer) -> None:
        self._container = container

    async def run_sync(self, run_id: uuid.UUID, max_vacancies: int | None = None) -> None:
        try:
            async with self._container() as scope:
                use_case = await scope.get(SyncVacanciesUseCase)
                await use_case.execute(run_id=run_id, max_vacancies=max_vacancies)
        except Exception:
            logger.exception("background sync job failed", extra={"run_id": str(run_id)})

    async def run_analysis(
        self,
        run_id: uuid.UUID,
        limit: int | None = None,
        external_id: str | None = None,
        force: bool = False,
    ) -> None:
        try:
            async with self._container() as scope:
                use_case = await scope.get(AnalyzeVacanciesUseCase)
                await use_case.execute(run_id=run_id, limit=limit, external_id=external_id, force=force)
        except Exception:
            logger.exception("background analysis job failed", extra={"run_id": str(run_id)})

    async def run_cycle(self) -> None:
        """Scheduled cycle: synchronization, analysis, report generation."""
        try:
            async with self._container() as scope:
                sync = await scope.get(SyncVacanciesUseCase)
                sync_result = await sync.execute()
                if sync_result.status not in {"success", "partial"}:
                    logger.warning(
                        "scheduled cycle stopped: sync did not succeed",
                        extra={"status": sync_result.status},
                    )
                    return

                analysis = await scope.get(AnalyzeVacanciesUseCase)
                await analysis.execute()

                report = await scope.get(GenerateReportUseCase)
                await report.execute()
        except Exception:
            logger.exception("scheduled cycle failed")
