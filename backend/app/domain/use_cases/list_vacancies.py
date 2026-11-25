from app.infrastructure.database.repositories.vacancy_repository import VacancyRepository
from app.schemas.vacancy import StoredVacancyDTO, VacancyListItemDTO, VacancyPageDTO


class ListVacanciesUseCase:
    """Returns a page of stored vacancies."""

    def __init__(self, vacancy_repository: VacancyRepository) -> None:
        self._vacancies = vacancy_repository

    async def execute(self, limit: int = 50, offset: int = 0) -> VacancyPageDTO:
        rows = await self._vacancies.list_page(limit=limit, offset=offset)
        total = await self._vacancies.count()
        return VacancyPageDTO(
            items=[self._to_item(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def _to_item(self, vacancy: StoredVacancyDTO) -> VacancyListItemDTO:
        return VacancyListItemDTO(
            id=vacancy.id,
            external_id=vacancy.external_id,
            title=vacancy.title,
            source_url=vacancy.source_url,
            company_name=vacancy.normalized.company_name,
            region_name=vacancy.normalized.region_name,
            salary=vacancy.normalized.salary,
            schedule=vacancy.normalized.schedule,
            employment_type=vacancy.normalized.employment_type,
            is_active=vacancy.is_active,
            updated_at=vacancy.updated_at,
        )
