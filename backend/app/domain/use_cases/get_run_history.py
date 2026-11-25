from app.infrastructure.database.repositories.analysis_run_repository import AnalysisRunRepository
from app.infrastructure.database.repositories.report_run_repository import ReportRunRepository
from app.infrastructure.database.repositories.sync_run_repository import SyncRunRepository
from app.schemas.api_response import RunDTO


class GetRunHistoryUseCase:
    """Returns the merged history of synchronization, analysis and report runs."""

    def __init__(
        self,
        sync_run_repository: SyncRunRepository,
        analysis_run_repository: AnalysisRunRepository,
        report_run_repository: ReportRunRepository,
    ) -> None:
        self._sync_runs = sync_run_repository
        self._analysis_runs = analysis_run_repository
        self._report_runs = report_run_repository

    async def execute(self, limit: int = 50) -> list[RunDTO]:
        runs: list[RunDTO] = []

        for run in await self._sync_runs.list(limit):
            runs.append(
                RunDTO(
                    kind="sync",
                    id=run.id,
                    status=run.status,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    processed_count=run.received_count,
                    failed_count=run.failed_count,
                    error_message=run.error_message,
                ),
            )

        for analysis_run in await self._analysis_runs.list(limit):
            runs.append(
                RunDTO(
                    kind="analysis",
                    id=analysis_run.id,
                    status=analysis_run.status,
                    started_at=analysis_run.started_at,
                    finished_at=analysis_run.finished_at,
                    processed_count=analysis_run.processed_count,
                    failed_count=analysis_run.failed_count,
                    error_message=analysis_run.error_message,
                ),
            )

        for report_run in await self._report_runs.list(limit):
            runs.append(
                RunDTO(
                    kind="report",
                    id=report_run.id,
                    status=report_run.status,
                    started_at=report_run.created_at,
                    finished_at=report_run.completed_at,
                    processed_count=report_run.vacancies_count,
                    failed_count=0,
                    error_message=report_run.error_message,
                ),
            )

        runs.sort(key=lambda run: run.started_at, reverse=True)
        return runs[:limit]
