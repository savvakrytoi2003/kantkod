from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Query

from app.domain.use_cases.get_vacancy import GetVacancyUseCase
from app.domain.use_cases.get_vacancy_issues import GetVacancyIssuesUseCase
from app.domain.use_cases.list_issue_vacancies import ListIssueVacanciesUseCase
from app.domain.use_cases.list_vacancies import ListVacanciesUseCase
from app.schemas.issue import IssueDTO
from app.schemas.issue_vacancy import IssueVacancyDTO
from app.schemas.vacancy import VacancyDetailDTO, VacancyPageDTO

router = APIRouter(prefix="/vacancies", tags=["vacancies"])


@router.get("", response_model=VacancyPageDTO)
@inject
async def list_vacancies(
    use_case: FromDishka[ListVacanciesUseCase],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> VacancyPageDTO:
    return await use_case.execute(limit=limit, offset=offset)


@router.get("/issues", response_model=list[IssueVacancyDTO])
@inject
async def list_vacancies_with_issues(
    use_case: FromDishka[ListIssueVacanciesUseCase],
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[IssueVacancyDTO]:
    """Vacancies that got at least one issue from the latest successful analysis."""
    return await use_case.execute(limit=limit, offset=offset)


@router.get("/{external_id}", response_model=VacancyDetailDTO)
@inject
async def get_vacancy(
    external_id: str,
    use_case: FromDishka[GetVacancyUseCase],
) -> VacancyDetailDTO:
    return await use_case.execute(external_id)


@router.get("/{external_id}/issues", response_model=list[IssueDTO])
@inject
async def get_vacancy_issues(
    external_id: str,
    use_case: FromDishka[GetVacancyIssuesUseCase],
) -> list[IssueDTO]:
    return await use_case.execute(external_id)
