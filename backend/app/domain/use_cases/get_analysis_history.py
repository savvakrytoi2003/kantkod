from app.infrastructure.database.repositories.analysis_run_repository import AnalysisRunRepository
from app.schemas.api_response import AnalysisRunDTO


class GetAnalysisHistoryUseCase:
    """Returns the history of analysis runs."""

    def __init__(self, analysis_run_repository: AnalysisRunRepository) -> None:
        self._runs = analysis_run_repository

    async def execute(self, limit: int = 50) -> list[AnalysisRunDTO]:
        return await self._runs.list(limit)
