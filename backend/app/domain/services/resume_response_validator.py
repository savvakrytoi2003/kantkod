import json
import re
from typing import Any

from pydantic import ValidationError

from app.domain.errors import AiResponseInvalidError
from app.schemas.resume import ResumeDraftContentDTO, ResumeGapStatus

_STATUS_ALIASES: dict[str, ResumeGapStatus] = {
    "matched": ResumeGapStatus.MATCHED,
    "match": ResumeGapStatus.MATCHED,
    "совпадает": ResumeGapStatus.MATCHED,
    "соответствует": ResumeGapStatus.MATCHED,
    "есть": ResumeGapStatus.MATCHED,
    "partial": ResumeGapStatus.PARTIAL,
    "частично": ResumeGapStatus.PARTIAL,
    "частичное": ResumeGapStatus.PARTIAL,
    "missing": ResumeGapStatus.MISSING,
    "miss": ResumeGapStatus.MISSING,
    "нет": ResumeGapStatus.MISSING,
    "отсутствует": ResumeGapStatus.MISSING,
    "не указано": ResumeGapStatus.MISSING,
}


class ResumeResponseValidator:
    """Парсит и нормализует JSON-ответ ИИ для черновика резюме."""

    def validate(self, raw: str | Any) -> ResumeDraftContentDTO:
        payload = self._parse(raw)
        if not isinstance(payload, dict):
            raise AiResponseInvalidError("Resume draft response must be a JSON object")

        for key in ("resume", "result", "data"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                payload = nested
                break

        if isinstance(payload.get("gaps"), list):
            for gap in payload["gaps"]:
                if isinstance(gap, dict):
                    gap["status"] = self._status(gap.get("status"))

        try:
            draft = ResumeDraftContentDTO.model_validate(payload)
        except ValidationError as exc:
            raise AiResponseInvalidError(f"Resume draft response is invalid: {exc}") from exc

        draft.summary = (draft.summary or "").strip()[:3000]
        draft.highlighted_skills = self._clean_list(draft.highlighted_skills, limit=20)
        draft.experience_highlights = self._clean_list(draft.experience_highlights, limit=15)
        draft.education_highlights = self._clean_list(draft.education_highlights, limit=10)
        draft.gaps = draft.gaps[:20]
        draft.draft_text = (draft.draft_text or "").strip()[:12000]

        if not draft.draft_text:
            draft.draft_text = self._fallback_text(draft)
        if not (draft.summary or draft.draft_text or draft.highlighted_skills or draft.gaps):
            raise AiResponseInvalidError("Resume draft response is empty")
        return draft

    def _parse(self, raw: str | Any) -> Any:
        if not isinstance(raw, str):
            return raw
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        start = min((index for index in (text.find("{"), text.find("[")) if index != -1), default=-1)
        if start > 0:
            text = text[start:]
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AiResponseInvalidError(f"Resume draft response is not valid JSON: {exc}") from exc

    def _status(self, value: Any) -> ResumeGapStatus:
        key = str(value or "").strip().lower()
        return _STATUS_ALIASES.get(key, ResumeGapStatus.MISSING)

    def _clean_list(self, values: list[str], limit: int) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = re.sub(r"\s+", " ", str(value)).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text[:500])
        return result[:limit]

    def _fallback_text(self, draft: ResumeDraftContentDTO) -> str:
        parts = [draft.summary] if draft.summary else []
        if draft.experience_highlights:
            parts.append("Опыт:\n" + "\n".join(f"- {item}" for item in draft.experience_highlights))
        if draft.education_highlights:
            parts.append("Образование:\n" + "\n".join(f"- {item}" for item in draft.education_highlights))
        if draft.highlighted_skills:
            parts.append("Навыки: " + ", ".join(draft.highlighted_skills))
        return "\n\n".join(parts)
