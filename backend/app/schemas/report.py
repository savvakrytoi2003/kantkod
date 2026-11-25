from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.issue import IssueDTO


class ReportVacancyDTO(BaseModel):
    vacancy_id: str
    name: str = ""
    source_url: str | None = None
    issues: list[IssueDTO] = Field(default_factory=list)


class ReportDTO(BaseModel):
    generated_at: datetime
    region: int
    vacancies: list[ReportVacancyDTO] = Field(default_factory=list)

    @property
    def issues_count(self) -> int:
        return sum(len(vacancy.issues) for vacancy in self.vacancies)
