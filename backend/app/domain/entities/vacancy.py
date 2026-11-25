from dataclasses import dataclass

from app.schemas.issue import IssueDTO
from app.schemas.vacancy import NormalizedVacancyDTO, StoredVacancyDTO


@dataclass(slots=True)
class VacancyCandidate:
    """Normalized vacancy prepared for persistence."""

    normalized: NormalizedVacancyDTO
    raw: dict
    content_hash: str

    @property
    def external_id(self) -> str:
        return self.normalized.external_id


@dataclass(slots=True)
class AnalysisTarget:
    """Vacancy that needs analysis together with the rule-based findings."""

    vacancy: StoredVacancyDTO
    rule_issues: list[IssueDTO]


@dataclass(slots=True)
class SyncCounters:
    received: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
