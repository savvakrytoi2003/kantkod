import uuid

from app.domain.use_cases.analyze_vacancies import AnalyzeVacanciesUseCase
from app.schemas.analysis import AnalysisResultDTO


class RetryAnalysisUseCase:
    """Forces a repeated analysis of a single vacancy."""

    def __init__(self, analyze_vacancies: AnalyzeVacanciesUseCase) -> None:
        self._analyze = analyze_vacancies

    async def prepare(self) -> uuid.UUID:
        return await self._analyze.prepare()

    async def execute(self, external_id: str, run_id: uuid.UUID | None = None) -> AnalysisResultDTO:
        return await self._analyze.execute(run_id=run_id, external_id=external_id, force=True)
