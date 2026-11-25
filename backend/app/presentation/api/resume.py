from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from app.domain.use_cases.generate_resume_draft import GenerateResumeDraftUseCase
from app.schemas.resume import ResumeDraftDTO, ResumeDraftRequestDTO

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/draft", response_model=ResumeDraftDTO)
@inject
async def generate_resume_draft(
    payload: ResumeDraftRequestDTO,
    use_case: FromDishka[GenerateResumeDraftUseCase],
) -> ResumeDraftDTO:
    """Build a resume draft for a vacancy using only the supplied resume facts."""
    return await use_case.execute(payload)
