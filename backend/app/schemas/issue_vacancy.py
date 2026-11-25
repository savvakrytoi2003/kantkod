from pydantic import BaseModel, Field

from app.schemas.issue import IssueDTO


class IssueVacancyDTO(BaseModel):
    vacancy_id: str
    title: str = ""
    company_name: str | None = None
    region_name: str | None = None
    source_url: str | None = None
    issues: list[IssueDTO] = Field(default_factory=list)
    issues_count: int = 0
