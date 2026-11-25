from app.infrastructure.cache.redis_vacancy_cache import RedisVacancyCache
from app.infrastructure.reports.report_writer import ReportWriter
from app.schemas.report import ReportDTO


class GetReportUseCase:
    """Returns the latest successful report from cache or from disk."""

    def __init__(self, cache: RedisVacancyCache, report_writer: ReportWriter) -> None:
        self._cache = cache
        self._writer = report_writer

    async def execute(self) -> ReportDTO | None:
        cached = await self._cache.get_report()
        if cached is not None:
            return cached

        report = self._writer.read_latest()
        if report is not None:
            await self._cache.set_report(report)
        return report
