import json
from pathlib import Path

from app.config.settings import Settings
from app.domain.services.ai_context_builder import AiContextBuilder
from app.domain.services.issue_merger import IssueMerger
from app.domain.services.report_builder import ReportBuilder
from app.domain.services.rule_checker import RuleChecker
from app.domain.services.source_payload_parser import SourcePayloadParser
from app.domain.services.vacancy_normalizer import VacancyNormalizer
from app.domain.use_cases.validate_json import ValidateJsonUseCase
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


async def test_validation_mode_processes_every_vacancy(tmp_path):
    output = tmp_path / "result.json"

    result = await _use_case(tmp_path / "reports").execute(str(SAMPLE), str(output))

    assert result.status == "success"
    assert result.vacancies_count == 10
    payload = json.loads(output.read_text(encoding="utf-8"))
    ids = [vacancy["vacancy_id"] for vacancy in payload["vacancies"]]
    assert len(ids) == 10
    assert len(set(ids)) == 10
    assert result.issues_count == sum(len(vacancy["issues"]) for vacancy in payload["vacancies"])


async def test_every_issue_has_required_fields(tmp_path):
    output = tmp_path / "result.json"

    await _use_case(tmp_path / "reports").execute(str(SAMPLE), str(output))

    payload = json.loads(output.read_text(encoding="utf-8"))
    for vacancy in payload["vacancies"]:
        for issue in vacancy["issues"]:
            assert issue["topic"]
            assert issue["source_field"]
            assert issue["problem"]
            assert issue["recommendation"]


async def test_repeated_run_keeps_one_entry_per_id(tmp_path):
    output = tmp_path / "result.json"
    use_case = _use_case(tmp_path / "reports")

    await use_case.execute(str(SAMPLE), str(output))
    await use_case.execute(str(SAMPLE), str(output))

    payload = json.loads(output.read_text(encoding="utf-8"))
    ids = [vacancy["vacancy_id"] for vacancy in payload["vacancies"]]
    assert len(ids) == len(set(ids))
