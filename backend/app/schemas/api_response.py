import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.report import ReportDTO


class SyncResultDTO(BaseModel):
    run_id: uuid.UUID
    status: str
    received_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    failed_count: int = 0
    error_message: str | None = None


class SyncRunDTO(BaseModel):
    id: uuid.UUID
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    received_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    failed_count: int = 0
    error_message: str | None = None


class AnalysisRunDTO(BaseModel):
    id: uuid.UUID
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    processed_count: int = 0
    failed_count: int = 0
    provider: str | None = None
    model_name: str | None = None
    error_message: str | None = None


class ReportRunDTO(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    report_path: str | None = None
    vacancies_count: int = 0
    issues_count: int = 0
    error_message: str | None = None


class RunDTO(BaseModel):
    kind: str
    id: uuid.UUID
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    processed_count: int = 0
    failed_count: int = 0
    error_message: str | None = None


class TaskAcceptedDTO(BaseModel):
    run_id: uuid.UUID
    status: str = "pending"


class HealthDTO(BaseModel):
    status: str
    version: str
    database: str
    redis: str
    scheduler: str


class ValidationResultDTO(BaseModel):
    status: str
    report_path: str
    vacancies_count: int = 0
    issues_count: int = 0


class PayloadAnalysisResultDTO(BaseModel):
    """Результат анализа загруженного JSON через пайплайн (без записи на диск)."""

    status: str = "success"
    report: ReportDTO
    ai_used: bool = False
    ai_failed: int = 0


class SyncStatusDTO(BaseModel):
    latest_run: SyncRunDTO | None = None


class ReportGenerationResultDTO(BaseModel):
    report_path: str
    vacancies_count: int = 0
    issues_count: int = 0
    run_id: uuid.UUID | None = None
    generated_at: datetime


class ErrorDTO(BaseModel):
    detail: str = Field(min_length=1)
