from app.schemas.analysis import AiVacancyContextDTO
from app.schemas.vacancy import NormalizedVacancyDTO


class AiContextBuilder:
    """Builds a compact vacancy context for the AI provider, limiting its size."""

    _DESCRIPTION_LIMIT = 2500
    _FIELD_LIMIT = 1200

    def build(self, vacancy: NormalizedVacancyDTO) -> AiVacancyContextDTO:
        return AiVacancyContextDTO(
            vacancy_id=vacancy.external_id,
            title=self._cut(vacancy.title, self._FIELD_LIMIT),
            duties=self._cut(vacancy.duties, self._FIELD_LIMIT),
            requirements=self._cut(self._join(vacancy.requirements, vacancy.qualification), self._FIELD_LIMIT),
            description=self._cut(vacancy.description, self._DESCRIPTION_LIMIT),
            salary=self._salary(vacancy),
            schedule=self._cut(vacancy.schedule or "", 300),
            shift=self._cut("; ".join(vacancy.shift), 300),
            employment=self._cut(vacancy.employment_type or "", 300),
            location=self._cut(vacancy.address or vacancy.work_place_type or "", 500),
            work_place_kind=self._cut(vacancy.work_place_kind or "", 300),
            salary_min=vacancy.salary.from_amount or 0,
            salary_max=vacancy.salary.to_amount or 0,
            currency=self._cut(vacancy.salary.currency or "", 50),
            experience=self._cut(vacancy.experience or "", 300),
            education=self._cut(vacancy.education or "", 300),
            qualification=self._cut(vacancy.qualification or "", self._FIELD_LIMIT),
            skills=self._cut("; ".join(vacancy.skills), 500),
        )

    def _salary(self, vacancy: NormalizedVacancyDTO) -> str:
        salary = vacancy.salary
        parts: list[str] = []
        if salary.from_amount is not None and salary.to_amount is not None:
            parts.append(f"от {salary.from_amount} до {salary.to_amount}")
        elif salary.from_amount is not None:
            parts.append(f"от {salary.from_amount}")
        elif salary.to_amount is not None:
            parts.append(f"до {salary.to_amount}")
        if salary.currency:
            parts.append(salary.currency)
        if salary.text and salary.text not in " ".join(parts):
            parts.append(f"({salary.text})")
        return " ".join(parts)[:300]

    def _join(self, *values: str | None) -> str:
        return " ".join(value.strip() for value in values if value and value.strip())

    def _cut(self, value: str, limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "…"
