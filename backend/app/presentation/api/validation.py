from typing import Any

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from app.domain.use_cases.validate_json import ValidateJsonUseCase
from app.schemas.api_response import PayloadAnalysisResultDTO, ValidationResultDTO
from app.schemas.requests import ValidationRequestDTO

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/run", response_model=ValidationResultDTO)
@inject
async def run_validation(
    payload: ValidationRequestDTO,
    use_case: FromDishka[ValidateJsonUseCase],
) -> ValidationResultDTO:
    return await use_case.execute(input_path=payload.input_path, output_path=payload.output_path)


@router.post("/analyze", response_model=PayloadAnalysisResultDTO)
@inject
async def analyze_uploaded_payload(
    payload: dict[str, Any],
    use_case: FromDishka[ValidateJsonUseCase],
) -> PayloadAnalysisResultDTO:
    """Analyze an uploaded JSON payload: rule checks plus optional AI, no files written."""
    return await use_case.analyze(payload)
