from app.infrastructure.database.repositories.vacancy_repository import VacancyRepository
from app.schemas.issue_vacancy import IssueVacancyDTO


class ListIssueVacanciesUseCase:
    """Returns vacancies that have at least one issue from the latest successful analysis."""

    def __init__(self, vacancy_repository: VacancyRepository) -> None:
        self._vacancies = vacancy_repository

    async def execute(self, limit: int = 100, offset: int = 0) -> list[IssueVacancyDTO]:
        rows = await self._vacancies.list_with_issues()
        items = [
            IssueVacancyDTO(
                vacancy_id=row.vacancy.external_id,
                title=row.vacancy.title,
                company_name=row.vacancy.normalized.company_name,
                region_name=row.vacancy.normalized.region_name,
                source_url=row.vacancy.source_url,
                issues=row.issues,
                issues_count=len(row.issues),
            )
            for row in rows
            if row.issues
        ]
        items.sort(key=lambda item: item.issues_count, reverse=True)
        return items[offset : offset + limit]
