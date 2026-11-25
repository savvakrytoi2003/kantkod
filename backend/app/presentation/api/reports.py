from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, HTTPException, status

from app.domain.use_cases.generate_report import GenerateReportUseCase
from app.domain.use_cases.get_report import GetReportUseCase
from app.schemas.api_response import ReportGenerationResultDTO
from app.schemas.report import ReportDTO

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/latest", response_model=ReportDTO)
@inject
async def latest_report(use_case: FromDishka[GetReportUseCase]) -> ReportDTO:
    report = await use_case.execute()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report is not generated yet")
    return report


@router.post("/generate", response_model=ReportGenerationResultDTO)
@inject
async def generate_report(use_case: FromDishka[GenerateReportUseCase]) -> ReportGenerationResultDTO:
    return await use_case.execute()
