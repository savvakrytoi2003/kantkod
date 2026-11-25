from pydantic import BaseModel, Field


class AnalysisRequestDTO(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=5000)
    force: bool = False


class SyncRequestDTO(BaseModel):
    max_vacancies: int | None = Field(default=None, ge=1, le=10000)


class ValidationRequestDTO(BaseModel):
    input_path: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
