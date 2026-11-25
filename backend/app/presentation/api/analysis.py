from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, BackgroundTasks, Request, status

from app.domain.use_cases.analyze_vacancies import AnalyzeVacanciesUseCase
from app.domain.use_cases.retry_analysis import RetryAnalysisUseCase
from app.infrastructure.jobs.job_runner import JobRunner
from app.schemas.api_response import TaskAcceptedDTO
from app.schemas.requests import AnalysisRequestDTO

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("", response_model=TaskAcceptedDTO, status_code=status.HTTP_202_ACCEPTED)
@inject
async def start_analysis(
    background_tasks: BackgroundTasks,
    request: Request,
    use_case: FromDishka[AnalyzeVacanciesUseCase],
    payload: AnalysisRequestDTO | None = None,
) -> TaskAcceptedDTO:
    run_id = await use_case.prepare()
    runner: JobRunner = request.app.state.job_runner
    background_tasks.add_task(
        runner.run_analysis,
        run_id,
        payload.limit if payload else None,
        None,
        payload.force if payload else False,
    )
    return TaskAcceptedDTO(run_id=run_id, status="pending")


@router.post("/{external_id}/retry", response_model=TaskAcceptedDTO, status_code=status.HTTP_202_ACCEPTED)
@inject
async def retry_analysis(
    external_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    use_case: FromDishka[RetryAnalysisUseCase],
) -> TaskAcceptedDTO:
    run_id = await use_case.prepare()
    runner: JobRunner = request.app.state.job_runner
    background_tasks.add_task(runner.run_analysis, run_id, None, external_id, True)
    return TaskAcceptedDTO(run_id=run_id, status="pending")
