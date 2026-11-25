import json
import logging
from pathlib import Path
from typing import Any

from app.config.settings import Settings
from app.domain.errors import InvalidSourcePayloadError
from app.domain.services.ai_context_builder import AiContextBuilder
from app.domain.services.issue_merger import IssueMerger, IssueVerifier
from app.domain.services.report_builder import ReportBuilder
from app.domain.services.rule_checker import RuleChecker
from app.domain.services.source_payload_parser import SourcePayloadParser
from app.domain.services.vacancy_normalizer import VacancyNormalizer
from app.infrastructure.ai.batch_vacancy_analyzer import BatchVacancyAnalyzer
from app.infrastructure.reports.report_writer import ReportWriter
from app.schemas.api_response import PayloadAnalysisResultDTO, ValidationResultDTO
from app.schemas.issue import IssueDTO
from app.schemas.report import ReportVacancyDTO

logger = logging.getLogger(__name__)

# Ограничение на файл, загруженный через API: ИИ-анализ больших файлов дорог и долог.
MAX_UPLOAD_VACANCIES = 200


class ValidateJsonUseCase:
    """Validation mode: analyzes a local JSON payload without calling the source portal."""

    def __init__(
        self,
        settings: Settings,
        parser: SourcePayloadParser,
        normalizer: VacancyNormalizer,
        rule_checker: RuleChecker,
        issue_merger: IssueMerger,
        context_builder: AiContextBuilder,
        ai_analyzer: BatchVacancyAnalyzer,
        report_builder: ReportBuilder,
        report_writer: ReportWriter,
    ) -> None:
        self._settings = settings
        self._parser = parser
        self._normalizer = normalizer
        self._rule_checker = rule_checker
        self._merger = issue_merger
        self._verifier = IssueVerifier()
        self._context_builder = context_builder
        self._ai = ai_analyzer
        self._report_builder = report_builder
        self._report_writer = report_writer

    async def execute(self, input_path: str, output_path: str) -> ValidationResultDTO:
        payload = self._load(input_path)
        result = await self._analyze(payload)
        path = self._report_writer.write_to(output_path, result.report)
        logger.info(
            "validation report written",
            extra={
                "path": str(path),
                "vacancies": len(result.report.vacancies),
                "issues": result.report.issues_count,
            },
        )
        return ValidationResultDTO(
            status=result.status,
            report_path=str(path),
            vacancies_count=len(result.report.vacancies),
            issues_count=result.report.issues_count,
        )

    async def analyze(self, payload: dict[str, Any]) -> PayloadAnalysisResultDTO:
        """Run the same pipeline for JSON uploaded through the API — no files, no database."""
        return await self._analyze(payload, max_vacancies=MAX_UPLOAD_VACANCIES)

    async def _analyze(
        self,
        payload: dict[str, Any],
        max_vacancies: int | None = None,
    ) -> PayloadAnalysisResultDTO:
        items = self._parser.parse(payload)
        if not items:
            raise InvalidSourcePayloadError("Payload contains no vacancies")
        if max_vacancies is not None and len(items) > max_vacancies:
            raise InvalidSourcePayloadError(
                f"Payload contains {len(items)} vacancies, the limit is {max_vacancies}",
            )

        rule_issues: dict[str, list[IssueDTO]] = {}
        source_urls: dict[str, str | None] = {}
        names: dict[str, str] = {}
        normalized_by_id = {}
        contexts = []

        for item in items:
            normalized = self._normalizer.normalize(item)
            if normalized is None:
                raise InvalidSourcePayloadError("Payload contains a vacancy without identifier")
            rule_issues[normalized.external_id] = self._rule_checker.check(normalized)
            source_urls[normalized.external_id] = normalized.source_url
            names[normalized.external_id] = normalized.title
            normalized_by_id[normalized.external_id] = normalized
            contexts.append(self._context_builder.build(normalized))

        ai_issues: dict[str, list[IssueDTO]] = {}
        ai_failures: dict[str, str] = {}

        if self._settings.ai_configured:
            logger.info("validation mode: sending vacancies to the AI provider", extra={"count": len(contexts)})
            batch = await self._ai.analyze(contexts)
            ai_issues = {result.vacancy_id: result.issues for result in batch.results}
            ai_failures = {failure.vacancy_id: failure.reason for failure in batch.failures}
        else:
            logger.warning("validation mode: AI provider is not configured, programmatic rules only")

        if ai_failures:
            details = "; ".join(f"{vacancy_id}: {reason}" for vacancy_id, reason in list(ai_failures.items())[:5])
            logger.warning(
                "validation mode: AI failed for some vacancies, programmatic rules are used",
                extra={"failed": len(ai_failures), "details": details},
            )

        entries = [
            ReportVacancyDTO(
                vacancy_id=external_id,
                name=names.get(external_id, ""),
                source_url=source_urls[external_id],
                issues=self._verifier.verify(
                    self._merger.merge(issues, ai_issues.get(external_id, [])),
                    normalized_by_id[external_id],
                ),
            )
            for external_id, issues in rule_issues.items()
        ]

        report = self._report_builder.build(entries, region=self._settings.source_region)
        return PayloadAnalysisResultDTO(
            status="partial" if ai_failures else "success",
            report=report,
            ai_used=self._settings.ai_configured,
            ai_failed=len(ai_failures),
        )

    def _load(self, input_path: str) -> dict:
        target = Path(input_path)
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except OSError as exc:
            raise InvalidSourcePayloadError(f"Cannot read input file {input_path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise InvalidSourcePayloadError(f"Input file {input_path} is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise InvalidSourcePayloadError("Input JSON must be an object")
        return payload
