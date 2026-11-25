import uuid

from pydantic import BaseModel, Field

from app.schemas.issue import IssueDTO


class AiVacancyContextDTO(BaseModel):
    """Compact vacancy projection that is sent to the AI provider."""

    vacancy_id: str
    title: str = ""
    duties: str = ""
    requirements: str = ""
    description: str = ""
    salary: str = ""
    salary_min: int = 0
    salary_max: int = 0
    currency: str = ""
    schedule: str = ""
    shift: str = ""
    employment: str = ""
    location: str = ""
    work_place_kind: str = ""
    experience: str = ""
    education: str = ""
    qualification: str = ""
    skills: str = ""


class VacancyIssuesDTO(BaseModel):
    vacancy_id: str
    issues: list[IssueDTO] = Field(default_factory=list)


class AiBatchResponseDTO(BaseModel):
    results: list[VacancyIssuesDTO] = Field(default_factory=list)


class BatchFailureDTO(BaseModel):
    vacancy_id: str
    reason: str


class BatchAnalysisResultDTO(BaseModel):
    results: list[VacancyIssuesDTO] = Field(default_factory=list)
    failures: list[BatchFailureDTO] = Field(default_factory=list)


class AnalysisResultDTO(BaseModel):
    run_id: uuid.UUID
    status: str
    processed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    issues_count: int = 0
