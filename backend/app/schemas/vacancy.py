import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.issue import IssueDTO


class SalaryDTO(BaseModel):
    from_amount: int | None = None
    to_amount: int | None = None
    currency: str | None = None
    gross: bool | None = None
    text: str | None = None

    @property
    def has_amounts(self) -> bool:
        return self.from_amount is not None or self.to_amount is not None


class NormalizedVacancyDTO(BaseModel):
    external_id: str
    title: str = ""
    description: str = ""
    duties: str = ""
    requirements: str = ""
    source_url: str | None = None
    salary: SalaryDTO = Field(default_factory=SalaryDTO)
    schedule: str | None = None
    shift: list[str] = Field(default_factory=list)
    employment_type: str | None = None
    work_place_type: str | None = None
    work_place_kind: str | None = None
    address: str | None = None
    region_code: str | None = None
    region_name: str | None = None
    company_name: str | None = None
    company_code: str | None = None
    experience: str | None = None
    education: str | None = None
    qualification: str | None = None
    skills: list[str] = Field(default_factory=list)
    published_at: str | None = None
    modified_at: str | None = None


class StoredVacancyDTO(BaseModel):
    id: uuid.UUID
    external_id: str
    source_url: str | None
    title: str
    description: str
    normalized: NormalizedVacancyDTO
    content_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_synced_at: datetime | None = None


class VacancyWithIssuesDTO(BaseModel):
    vacancy: StoredVacancyDTO
    issues: list[IssueDTO] = Field(default_factory=list)


class VacancyListItemDTO(BaseModel):
    id: uuid.UUID
    external_id: str
    title: str
    source_url: str | None = None
    company_name: str | None = None
    region_name: str | None = None
    salary: SalaryDTO = Field(default_factory=SalaryDTO)
    schedule: str | None = None
    employment_type: str | None = None
    is_active: bool = True
    updated_at: datetime


class VacancyDetailDTO(BaseModel):
    vacancy: StoredVacancyDTO
    issues: list[IssueDTO] = Field(default_factory=list)


class VacancyPageDTO(BaseModel):
    items: list[VacancyListItemDTO] = Field(default_factory=list)
    total: int = 0
    limit: int = 0
    offset: int = 0
