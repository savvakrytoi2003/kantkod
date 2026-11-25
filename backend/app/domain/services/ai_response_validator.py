import re
from typing import Any, ClassVar

from pydantic import ValidationError

from app.domain.errors import AiResponseInvalidError
from app.schemas.analysis import VacancyIssuesDTO
from app.schemas.issue import IssueDTO, IssueTopic


class AiResponseValidator:
    """Validates and normalizes AI responses against the expected schema."""

    _TOPIC_ALIASES: ClassVar[dict[str, IssueTopic]] = {
        "work_place": IssueTopic.LOCATION,
        "workplace": IssueTopic.LOCATION,
        "place": IssueTopic.LOCATION,
        "address": IssueTopic.LOCATION,
        "location_details": IssueTopic.LOCATION,
        "salary_conditions": IssueTopic.SALARY,
        "payment": IssueTopic.SALARY,
        "pay": IssueTopic.SALARY,
        "зарплата": IssueTopic.SALARY,
        "оплата": IssueTopic.SALARY,
        "work_schedule": IssueTopic.SCHEDULE,
        "график": IssueTopic.SCHEDULE,
        "employment_type": IssueTopic.EMPLOYMENT,
        "занятость": IssueTopic.EMPLOYMENT,
        "job_title": IssueTopic.TITLE,
        "position": IssueTopic.TITLE,
        "должность": IssueTopic.TITLE,
        "responsibilities": IssueTopic.DUTIES,
        "обязанности": IssueTopic.DUTIES,
        "requirement": IssueTopic.REQUIREMENTS,
        "требования": IssueTopic.REQUIREMENTS,
        "inconsistency": IssueTopic.CONTRADICTION,
        "consistency": IssueTopic.CONTRADICTION,
        "противоречие": IssueTopic.CONTRADICTION,
        "description": IssueTopic.OTHER,
        "general": IssueTopic.OTHER,
        "прочее": IssueTopic.OTHER,
        "conflict": IssueTopic.CONTRADICTION,
        "contradictions": IssueTopic.CONTRADICTION,
    }

    def validate(
        self,
        payload: Any,
        requested_ids: set[str],
    ) -> tuple[list[VacancyIssuesDTO], list[str]]:
        raw_results = self._extract_results(payload)

        by_id: dict[str, list[IssueDTO]] = {}

        for entry in raw_results:
            if not isinstance(entry, dict):
                raise AiResponseInvalidError("AI response entry is not an object")
            vacancy_id = self._vacancy_id(entry)
            if not vacancy_id or vacancy_id not in requested_ids:
                continue
            by_id.setdefault(vacancy_id, []).extend(self._validate_issues(entry.get("issues")))

        missing = sorted(requested_ids - set(by_id))
        validated = [VacancyIssuesDTO(vacancy_id=vacancy_id, issues=issues) for vacancy_id, issues in by_id.items()]
        return validated, missing

    def _extract_results(self, payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            raise AiResponseInvalidError("AI response must be a JSON object")

        for key in ("results", "vacancies", "analyses", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

        if "vacancy_id" in payload or "issues" in payload:
            return [payload]

        raise AiResponseInvalidError("AI response has no results list")

    def _vacancy_id(self, entry: dict[str, Any]) -> str:
        for key in ("vacancy_id", "id", "vacancyId"):
            value = entry.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    def _validate_issues(self, raw_issues: Any) -> list[IssueDTO]:
        if raw_issues is None:
            return []
        if not isinstance(raw_issues, list):
            raise AiResponseInvalidError("'issues' must be a list")

        issues: list[IssueDTO] = []
        for raw in raw_issues:
            if not isinstance(raw, dict):
                continue
            try:
                issue = IssueDTO.model_validate(self._normalize_issue(raw))
            except (ValidationError, ValueError):
                continue
            if not self._is_consistent(issue):
                continue
            issues.append(issue)
        return issues

    def _normalize_issue(self, raw: dict[str, Any]) -> dict[str, Any]:
        topic = self._topic(raw.get("topic"))
        return {
            "topic": topic,
            "source_field": str(raw.get("source_field") or raw.get("field") or topic.value).strip(),
            "quote": self._text(raw.get("quote")),
            "problem": self._text(raw.get("problem") or raw.get("issue")),
            "recommendation": self._text(raw.get("recommendation") or raw.get("suggestion")),
        }

    def _topic(self, raw_topic: Any) -> IssueTopic:
        value = self._text(raw_topic).lower().replace(" ", "_").replace("-", "_")
        if value in self._TOPIC_ALIASES:
            return self._TOPIC_ALIASES[value]
        try:
            return IssueTopic(value)
        except ValueError:
            return IssueTopic.OTHER

    def _is_consistent(self, issue: IssueDTO) -> bool:
        quote = issue.quote.strip()
        if issue.topic is IssueTopic.CONTRADICTION:
            parts = [part.strip() for part in re.split(r"\s+/\s+|[|;]", quote) if part.strip()]
            return len(parts) >= 2
        # Пустая цитата допустима и проверяется позже по полям вакансии:
        # здесь эвристики на текст проблемы слишком часто отбрасывали валидные замечания.
        return True

    def _text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return "; ".join(str(item).strip() for item in value if str(item).strip())
        return str(value).strip()
