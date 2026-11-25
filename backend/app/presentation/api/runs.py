import uuid

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Query

from app.domain.use_cases.get_run import GetRunUseCase
from app.domain.use_cases.get_run_history import GetRunHistoryUseCase
from app.schemas.api_response import RunDTO

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[RunDTO])
@inject
async def list_runs(
    use_case: FromDishka[GetRunHistoryUseCase],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RunDTO]:
    return await use_case.execute(limit=limit)


@router.get("/{run_id}", response_model=RunDTO)
@inject
async def get_run(run_id: uuid.UUID, use_case: FromDishka[GetRunUseCase]) -> RunDTO:
    return await use_case.execute(run_id)
