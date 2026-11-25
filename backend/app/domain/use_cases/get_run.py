import uuid

from app.domain.errors import KantKodError
from app.infrastructure.database.repositories.analysis_run_repository import AnalysisRunRepository
from app.infrastructure.database.repositories.report_run_repository import ReportRunRepository
from app.infrastructure.database.repositories.sync_run_repository import SyncRunRepository
from app.schemas.api_response import RunDTO


class GetRunUseCase:
    """Finds a run by its identifier across all run types."""

    def __init__(
        self,
        sync_run_repository: SyncRunRepository,
        analysis_run_repository: AnalysisRunRepository,
        report_run_repository: ReportRunRepository,
    ) -> None:
        self._sync_runs = sync_run_repository
        self._analysis_runs = analysis_run_repository
        self._report_runs = report_run_repository

    async def execute(self, run_id: uuid.UUID) -> RunDTO:
        sync_run = await self._sync_runs.get(run_id)
        if sync_run is not None:
            return RunDTO(
                kind="sync",
                id=sync_run.id,
                status=sync_run.status,
                started_at=sync_run.started_at,
                finished_at=sync_run.finished_at,
                processed_count=sync_run.received_count,
                failed_count=sync_run.failed_count,
                error_message=sync_run.error_message,
            )

        analysis_run = await self._analysis_runs.get(run_id)
        if analysis_run is not None:
            return RunDTO(
                kind="analysis",
                id=analysis_run.id,
                status=analysis_run.status,
                started_at=analysis_run.started_at,
                finished_at=analysis_run.finished_at,
                processed_count=analysis_run.processed_count,
                failed_count=analysis_run.failed_count,
                error_message=analysis_run.error_message,
            )

        report_run = await self._report_runs.get(run_id)
        if report_run is not None:
            return RunDTO(
                kind="report",
                id=report_run.id,
                status=report_run.status,
                started_at=report_run.created_at,
                finished_at=report_run.completed_at,
                processed_count=report_run.vacancies_count,
                failed_count=0,
                error_message=report_run.error_message,
            )

        raise KantKodError(f"Run {run_id} is not found")
