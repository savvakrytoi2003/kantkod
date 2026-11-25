from enum import StrEnum

from pydantic import BaseModel, Field


class IssueTopic(StrEnum):
    TITLE = "title"
    DUTIES = "duties"
    REQUIREMENTS = "requirements"
    SALARY = "salary"
    SCHEDULE = "schedule"
    LOCATION = "location"
    EMPLOYMENT = "employment"
    CONTRADICTION = "contradiction"
    OTHER = "other"


class IssueDTO(BaseModel):
    topic: IssueTopic
    source_field: str = Field(min_length=1)
    quote: str = ""
    problem: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
