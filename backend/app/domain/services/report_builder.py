from datetime import UTC, datetime

from app.schemas.report import ReportDTO, ReportVacancyDTO


class ReportBuilder:
    """Builds the JSON report model from vacancies and their issues."""

    def build(
        self,
        vacancies: list[ReportVacancyDTO],
        region: int,
        generated_at: datetime | None = None,
    ) -> ReportDTO:
        unique: dict[str, ReportVacancyDTO] = {}
        for vacancy in vacancies:
            existing = unique.get(vacancy.vacancy_id)
            if existing is None:
                unique[vacancy.vacancy_id] = vacancy
                continue
            existing.issues.extend(vacancy.issues)

        return ReportDTO(
            generated_at=generated_at or datetime.now(tz=UTC),
            region=region,
            vacancies=list(unique.values()),
        )
