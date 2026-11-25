from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, BackgroundTasks, Request, status

from app.domain.use_cases.get_sync_status import GetSyncStatusUseCase
from app.domain.use_cases.sync_vacancies import SyncVacanciesUseCase
from app.infrastructure.jobs.job_runner import JobRunner
from app.schemas.api_response import SyncStatusDTO, TaskAcceptedDTO
from app.schemas.requests import SyncRequestDTO

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("", response_model=TaskAcceptedDTO, status_code=status.HTTP_202_ACCEPTED)
@inject
async def start_sync(
    background_tasks: BackgroundTasks,
    request: Request,
    use_case: FromDishka[SyncVacanciesUseCase],
    payload: SyncRequestDTO | None = None,
) -> TaskAcceptedDTO:
    run_id = await use_case.prepare()
    runner: JobRunner = request.app.state.job_runner
    background_tasks.add_task(runner.run_sync, run_id, payload.max_vacancies if payload else None)
    return TaskAcceptedDTO(run_id=run_id, status="pending")


@router.get("/status", response_model=SyncStatusDTO)
@inject
async def sync_status(use_case: FromDishka[GetSyncStatusUseCase]) -> SyncStatusDTO:
    return await use_case.execute()
