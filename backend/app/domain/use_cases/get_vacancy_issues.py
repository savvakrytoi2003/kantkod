from app.domain.use_cases.get_vacancy import GetVacancyUseCase
from app.schemas.issue import IssueDTO


class GetVacancyIssuesUseCase:
    """Returns the issues of the latest successful analysis for a vacancy."""

    def __init__(self, get_vacancy: GetVacancyUseCase) -> None:
        self._get_vacancy = get_vacancy

    async def execute(self, external_id: str) -> list[IssueDTO]:
        detail = await self._get_vacancy.execute(external_id)
        return detail.issues
