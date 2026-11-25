import json
from pathlib import Path

import pytest

from app.config.settings import Settings
from app.domain.errors import InvalidSourcePayloadError
from app.domain.services.ai_context_builder import AiContextBuilder
from app.domain.services.issue_merger import IssueMerger
from app.domain.services.report_builder import ReportBuilder
from app.domain.services.rule_checker import RuleChecker
from app.domain.services.source_payload_parser import SourcePayloadParser
from app.domain.services.vacancy_normalizer import VacancyNormalizer
from app.domain.use_cases.validate_json import MAX_UPLOAD_VACANCIES, ValidateJsonUseCase
from app.infrastructure.reports.report_writer import ReportWriter

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "sample.json"


class _AiMustNotBeCalled:
    async def analyze(self, contexts):  # pragma: no cover - guards the disabled-AI path
        raise AssertionError("AI must not be called when it is not configured")


def _use_case(reports_dir: Path) -> ValidateJsonUseCase:
    settings = Settings(ai_enabled=False, reports_dir=str(reports_dir))
    return ValidateJsonUseCase(
        settings=settings,
        parser=SourcePayloadParser(),
        normalizer=VacancyNormalizer(),
        rule_checker=RuleChecker(),
        issue_merger=IssueMerger(),
        context_builder=AiContextBuilder(),
        ai_analyzer=_AiMustNotBeCalled(),
        report_builder=ReportBuilder(),
        report_writer=ReportWriter(settings),
    )


def _sample_payload() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


async def test_analyze_returns_report_without_writing_files(tmp_path):
    use_case = _use_case(tmp_path / "reports")

    result = await use_case.analyze(_sample_payload())

    assert result.status == "success"
    assert result.ai_used is False
    assert len(result.report.vacancies) == 10
    assert result.report.region == 39
    assert result.report.issues_count > 0
    assert not list(tmp_path.rglob("*.json"))


async def test_analyze_rejects_payload_without_vacancies(tmp_path):
    use_case = _use_case(tmp_path / "reports")

    with pytest.raises(InvalidSourcePayloadError):
        await use_case.analyze({"results": {"vacancies": []}})


async def test_analyze_rejects_payload_over_limit(tmp_path):
    use_case = _use_case(tmp_path / "reports")
    vacancy = _sample_payload()["results"]["vacancies"][0]
    payload = {"results": {"vacancies": [vacancy] * (MAX_UPLOAD_VACANCIES + 1)}}

    with pytest.raises(InvalidSourcePayloadError):
        await use_case.analyze(payload)


async def test_analyzed_issues_have_required_fields(tmp_path):
    use_case = _use_case(tmp_path / "reports")

    result = await use_case.analyze(_sample_payload())

    for vacancy in result.report.vacancies:
        for issue in vacancy.issues:
            assert issue.topic
            assert issue.source_field
            assert issue.problem
            assert issue.recommendation
