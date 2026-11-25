import logging

from app.config.settings import Settings
from app.domain.errors import ReportGenerationError
from app.domain.services.report_builder import ReportBuilder
from app.infrastructure.cache.redis_vacancy_cache import RedisVacancyCache
from app.infrastructure.database.repositories.report_run_repository import ReportRunRepository
from app.infrastructure.database.repositories.vacancy_repository import VacancyRepository
from app.infrastructure.reports.report_writer import ReportWriter
from app.schemas.api_response import ReportGenerationResultDTO
from app.schemas.report import ReportVacancyDTO

logger = logging.getLogger(__name__)


class GenerateReportUseCase:
    """Builds the JSON report and stores it as the latest successful report."""

    def __init__(
        self,
        settings: Settings,
        vacancy_repository: VacancyRepository,
        report_builder: ReportBuilder,
        report_writer: ReportWriter,
        report_run_repository: ReportRunRepository,
        cache: RedisVacancyCache,
    ) -> None:
        self._settings = settings
        self._vacancies = vacancy_repository
        self._builder = report_builder
        self._writer = report_writer
        self._runs = report_run_repository
        self._cache = cache

    async def execute(self) -> ReportGenerationResultDTO:
        run_id = await self._runs.start()
        try:
            rows = await self._vacancies.list_with_issues()
            entries = [
                ReportVacancyDTO(
                    vacancy_id=row.vacancy.external_id,
                    name=row.vacancy.title,
                    source_url=row.vacancy.source_url,
                    issues=row.issues,
                )
                for row in rows
            ]
            report = self._builder.build(entries, region=self._settings.source_region)
            path = self._writer.write(report)
            self._writer.write_latest(report)
            await self._cache.set_report(report)
            await self._runs.finish(
                run_id,
                "success",
                str(path),
                len(report.vacancies),
                report.issues_count,
            )
        except Exception as exc:
            logger.exception("report generation failed")
            await self._runs.finish(run_id, "failed", error_message=f"{type(exc).__name__}: {exc}")
            raise ReportGenerationError(f"Report generation failed: {exc}") from exc

        logger.info(
            "report generated",
            extra={"path": str(path), "vacancies": len(report.vacancies), "issues": report.issues_count},
        )
        return ReportGenerationResultDTO(
            report_path=str(path),
            vacancies_count=len(report.vacancies),
            issues_count=report.issues_count,
            run_id=run_id,
            generated_at=report.generated_at,
        )
