from app.domain.errors import VacancyNotFoundError
from app.infrastructure.cache.redis_vacancy_cache import RedisVacancyCache
from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.database.repositories.vacancy_repository import VacancyRepository
from app.schemas.vacancy import VacancyDetailDTO


class GetVacancyUseCase:
    """Returns a vacancy from Redis cache or PostgreSQL."""

    def __init__(
        self,
        vacancy_repository: VacancyRepository,
        analysis_repository: AnalysisRepository,
        cache: RedisVacancyCache,
    ) -> None:
        self._vacancies = vacancy_repository
        self._analyses = analysis_repository
        self._cache = cache

    async def execute(self, external_id: str) -> VacancyDetailDTO:
        cached = await self._cache.get_vacancy(external_id)
        if cached is not None:
            return cached

        vacancy = await self._vacancies.get_by_external_id(external_id)
        if vacancy is None:
            raise VacancyNotFoundError(f"Vacancy {external_id} is not found")

        issues = await self._analyses.latest_issues(vacancy.id)
        detail = VacancyDetailDTO(vacancy=vacancy, issues=issues)
        await self._cache.set_vacancy(external_id, detail)
        return detail
