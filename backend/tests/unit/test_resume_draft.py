import json
import uuid
from datetime import UTC, datetime

import pytest

from app.config.settings import Settings
from app.domain.errors import InvalidResumeError, VacancyNotFoundError
from app.domain.services.resume_prompt_builder import ResumePromptBuilder
from app.domain.services.resume_response_validator import ResumeResponseValidator
from app.domain.use_cases.generate_resume_draft import GenerateResumeDraftUseCase
from app.schemas.resume import (
    ResumeDraftRequestDTO,
    ResumeDTO,
    ResumeExperienceDTO,
    ResumeGapStatus,
)
from app.schemas.vacancy import NormalizedVacancyDTO, StoredVacancyDTO

VALID = {
    "summary": "Секретарь с опытом документооборота и 1С.",
    "highlighted_skills": ["1С:Документооборот", "MS Office"],
    "experience_highlights": ["Вела электронный архив в ООО «Морской бриз»"],
    "education_highlights": ["БФУ им. Канта, документоведение"],
    "gaps": [
        {"requirement": "Опыт от 1 года", "status": "matched", "advice": "Подтверждено резюме"},
        {"requirement": "Английский B2", "status": "missing", "advice": "Уточните уровень, если он выше B1"},
    ],
    "draft_text": "# Анна Иванова\n\n## Опыт\n- Вела электронный архив",
}


def _vacancy() -> StoredVacancyDTO:
    now = datetime.now(tz=UTC)
    return StoredVacancyDTO(
        id=uuid.uuid4(),
        external_id="DEMO-39-001",
        source_url="https://trudvsem.ru/vacancy/card/DEMO-39/DEMO-39-001",
        title="Специалист по документообороту",
        description="",
        normalized=NormalizedVacancyDTO(
            external_id="DEMO-39-001",
            title="Специалист по документообороту",
            duties="Регистрация корреспонденции, ведение архива.",
            requirements="Среднее профессиональное образование, 1С.",
            schedule="Полный рабочий день, 09:00–18:00",
            employment_type="Полная занятость",
            address="г. Калининград, ул. Ленина, 1",
            company_name="ООО «Балтика»",
            region_name="Калининградская область",
        ),
        content_hash="hash",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


class _VacancyRepository:
    def __init__(self, vacancy: StoredVacancyDTO | None) -> None:
        self._vacancy = vacancy

    async def get_by_external_id(self, external_id: str) -> StoredVacancyDTO | None:
        if self._vacancy and self._vacancy.external_id == external_id:
            return self._vacancy
        return None


class _FakeAi:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        assert "ТОЛЬКО факты" in system_prompt
        assert "Специалист по документообороту" in user_prompt
        return self._responses.pop(0)


def _settings() -> Settings:
    return Settings(
        ai_enabled=True,
        ai_api_key="test",
        ai_base_url="https://api.deepseek.com",
        ai_model="deepseek-flash",
    )


def _use_case(ai: _FakeAi, vacancy: StoredVacancyDTO | None = None) -> GenerateResumeDraftUseCase:
    return GenerateResumeDraftUseCase(
        settings=_settings(),
        vacancy_repository=_VacancyRepository(vacancy or _vacancy()),
        ai_client=ai,
        prompt_builder=ResumePromptBuilder(),
        validator=ResumeResponseValidator(),
    )


def _resume() -> ResumeDTO:
    return ResumeDTO(
        full_name="Анна Иванова",
        target_position="Специалист по документообороту",
        experience=[
            ResumeExperienceDTO(
                company="ООО «Морской бриз»",
                position="Секретарь-делопроизводитель",
                period="2021–2024",
                description="Ведение документооборота и электронного архива.",
            ),
        ],
        skills=["1С:Документооборот", "MS Office"],
        languages=["английский — B1"],
    )


async def test_generates_draft_with_vacancy_metadata() -> None:
    ai = _FakeAi([json.dumps(VALID, ensure_ascii=False)])

    result = await _use_case(ai).execute(
        ResumeDraftRequestDTO(vacancy_id="DEMO-39-001", resume=_resume()),
    )

    assert ai.calls == 1
    assert result.vacancy_title == "Специалист по документообороту"
    assert result.company_name == "ООО «Балтика»"
    assert result.summary.startswith("Секретарь")
    assert result.gaps[0].status is ResumeGapStatus.MATCHED
    assert result.gaps[1].status is ResumeGapStatus.MISSING
    assert result.draft_text
    assert len(result.notes) == 2


async def test_accepts_plain_text_resume() -> None:
    ai = _FakeAi([json.dumps(VALID, ensure_ascii=False)])
    text = "Анна Иванова, секретарь-делопроизводитель, опыт 3 года, 1С и MS Office."

    result = await _use_case(ai).execute(
        ResumeDraftRequestDTO(vacancy_id="DEMO-39-001", resume=text),
    )

    assert result.vacancy_id == "DEMO-39-001"


async def test_repairs_invalid_ai_response() -> None:
    ai = _FakeAi(["не JSON", json.dumps(VALID, ensure_ascii=False)])

    result = await _use_case(ai).execute(
        ResumeDraftRequestDTO(vacancy_id="DEMO-39-001", resume=_resume()),
    )

    assert ai.calls == 2
    assert result.vacancy_title


async def test_rejects_empty_resume() -> None:
    ai = _FakeAi([])

    with pytest.raises(InvalidResumeError):
        await _use_case(ai).execute(
            ResumeDraftRequestDTO(vacancy_id="DEMO-39-001", resume=ResumeDTO(full_name="Анна")),
        )


async def test_rejects_unknown_vacancy() -> None:
    ai = _FakeAi([])

    with pytest.raises(VacancyNotFoundError):
        await _use_case(ai, vacancy=None).execute(
            ResumeDraftRequestDTO(vacancy_id="NOPE", resume=_resume()),
        )


def test_validator_handles_fences_and_status_aliases() -> None:
    raw = (
        "```json\n"
        + json.dumps(
            {
                "summary": "Кратко",
                "gaps": [{"requirement": "Английский", "status": "частично", "advice": "Уточнить"}],
            },
            ensure_ascii=False,
        )
        + "\n```"
    )

    draft = ResumeResponseValidator().validate(raw)

    assert draft.gaps[0].status is ResumeGapStatus.PARTIAL
    assert draft.draft_text


def test_validator_builds_fallback_draft() -> None:
    draft = ResumeResponseValidator().validate(
        {
            "summary": "Кратко о кандидате",
            "highlighted_skills": ["1С"],
            "experience_highlights": ["Опыт работы секретарём"],
            "gaps": [],
        },
    )

    assert "Опыт работы секретарём" in draft.draft_text
    assert "1С" in draft.draft_text
