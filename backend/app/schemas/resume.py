from enum import StrEnum

from pydantic import BaseModel, Field

MAX_RESUME_TEXT = 12_000


class ResumeExperienceDTO(BaseModel):
    company: str = Field(default="", max_length=300)
    position: str = Field(default="", max_length=300)
    period: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=3_000)
    achievements: list[str] = Field(default_factory=list)


class ResumeEducationDTO(BaseModel):
    institution: str = Field(default="", max_length=300)
    specialty: str = Field(default="", max_length=300)
    year: str = Field(default="", max_length=20)


class ResumeDTO(BaseModel):
    """Резюме соискателя: структурированные поля и/или свободный текст."""

    full_name: str = Field(default="", max_length=200)
    target_position: str = Field(default="", max_length=300)
    summary: str = Field(default="", max_length=3_000)
    experience: list[ResumeExperienceDTO] = Field(default_factory=list)
    education: list[ResumeEducationDTO] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certificates: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    text: str = Field(default="", max_length=MAX_RESUME_TEXT)


class ResumeDraftRequestDTO(BaseModel):
    vacancy_id: str = Field(min_length=1, max_length=128)
    resume: ResumeDTO | str


class ResumeGapStatus(StrEnum):
    MATCHED = "matched"
    PARTIAL = "partial"
    MISSING = "missing"


class ResumeGapDTO(BaseModel):
    requirement: str = Field(min_length=1, max_length=500)
    status: ResumeGapStatus = ResumeGapStatus.MISSING
    advice: str = Field(default="", max_length=1_000)


class ResumeDraftContentDTO(BaseModel):
    """Ответ ИИ без данных вакансии — валидируется отдельно."""

    summary: str = ""
    highlighted_skills: list[str] = Field(default_factory=list)
    experience_highlights: list[str] = Field(default_factory=list)
    education_highlights: list[str] = Field(default_factory=list)
    gaps: list[ResumeGapDTO] = Field(default_factory=list)
    draft_text: str = ""


class ResumeDraftDTO(BaseModel):
    vacancy_id: str
    vacancy_title: str
    company_name: str | None = None
    source_url: str | None = None
    summary: str
    highlighted_skills: list[str] = Field(default_factory=list)
    experience_highlights: list[str] = Field(default_factory=list)
    education_highlights: list[str] = Field(default_factory=list)
    gaps: list[ResumeGapDTO] = Field(default_factory=list)
    draft_text: str
    notes: list[str] = Field(default_factory=list)
