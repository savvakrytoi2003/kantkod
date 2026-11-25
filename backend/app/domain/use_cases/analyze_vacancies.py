import logging
import uuid

from app.config.settings import Settings
from app.domain.errors import VacancyNotFoundError
from app.domain.services.ai_context_builder import AiContextBuilder
from app.domain.services.issue_merger import IssueMerger, IssueVerifier
from app.domain.services.rule_checker import RuleChecker
from app.infrastructure.ai.batch_vacancy_analyzer import BatchVacancyAnalyzer
from app.infrastructure.cache.redis_vacancy_cache import RedisVacancyCache
from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.database.repositories.analysis_run_repository import AnalysisRunRepository
from app.infrastructure.database.repositories.vacancy_repository import VacancyRepository
from app.schemas.analysis import AnalysisResultDTO
from app.schemas.issue import IssueDTO
from app.schemas.vacancy import StoredVacancyDTO

logger = logging.getLogger(__name__)


class AnalyzeVacanciesUseCase:
    """Analyzes vacancies that need analysis using programmatic rules and the AI provider."""

    _DEFAULT_LIMIT = 200

    def __init__(
        self,
        settings: Settings,
        vacancy_repository: VacancyRepository,
        analysis_repository: AnalysisRepository,
        analysis_run_repository: AnalysisRunRepository,
        rule_checker: RuleChecker,
        issue_merger: IssueMerger,
        context_builder: AiContextBuilder,
        ai_analyzer: BatchVacancyAnalyzer,
        cache: RedisVacancyCache,
    ) -> None:
        self._settings = settings
        self._vacancies = vacancy_repository
        self._analyses = analysis_repository
        self._runs = analysis_run_repository
        self._rule_checker = rule_checker
        self._merger = issue_merger
        self._verifier = IssueVerifier()
        self._context_builder = context_builder
        self._ai = ai_analyzer
        self._cache = cache

    async def prepare(self) -> uuid.UUID:
        run = await self._runs.start(
            provider=self._settings.ai_provider,
            model_name=self._settings.ai_model or None,
            status="pending",
        )
        logger.info("analysis run prepared", extra={"run_id": str(run.id)})
        return run.id

    async def execute(
        self,
        run_id: uuid.UUID | None = None,
        limit: int | None = None,
        external_id: str | None = None,
        force: bool = False,
    ) -> AnalysisResultDTO:
        run = run_id
        if run is None:
            run = (
                await self._runs.start(
                    provider=self._settings.ai_provider,
                    model_name=self._settings.ai_model or None,
                    status="running",
                )
            ).id
        else:
            await self._runs.finish(run, "running", 0, 0)

        try:
            candidates = await self._collect_candidates(limit, external_id, force)
            return await self._analyze(run, candidates)
        except Exception as exc:
            logger.exception("analysis failed", extra={"run_id": str(run)})
            await self._runs.finish(run, "failed", 0, 0, f"{type(exc).__name__}: {exc}")
            raise

    async def _collect_candidates(
        self,
        limit: int | None,
        external_id: str | None,
        force: bool,
    ) -> list[tuple[StoredVacancyDTO, list[IssueDTO]]]:
        if external_id:
            vacancy = await self._vacancies.get_by_external_id(external_id)
            if vacancy is None:
                raise VacancyNotFoundError(f"Vacancy {external_id} is not found")
            vacancies = [vacancy]
        else:
            vacancies = await self._vacancies.list_pending_analysis(
                limit or self._DEFAULT_LIMIT,
                include_analyzed=force,
            )

        candidates: list[tuple[StoredVacancyDTO, list[IssueDTO]]] = []
        skipped = 0
        for vacancy in vacancies:
            if not force and await self._analyses.has_success(vacancy.id, vacancy.content_hash):
                skipped += 1
                continue
            candidates.append((vacancy, self._rule_checker.check(vacancy.normalized)))

        logger.info(
            "analysis candidates collected",
            extra={"candidates": len(candidates), "skipped": skipped},
        )
        return candidates

    async def _analyze(
        self,
        run: uuid.UUID,
        candidates: list[tuple[StoredVacancyDTO, list[IssueDTO]]],
    ) -> AnalysisResultDTO:
        if not candidates:
            await self._runs.finish(run, "success", 0, 0)
            return AnalysisResultDTO(run_id=run, status="success")

        ai_issues: dict[str, list[IssueDTO]] = {}
        ai_failures: dict[str, str] = {}
        ai_state = "success"

        if self._settings.ai_configured:
            contexts = [self._context_builder.build(vacancy.normalized) for vacancy, _ in candidates]
            logger.info("analysis started", extra={"run_id": str(run), "vacancies": len(contexts)})
            batch = await self._ai.analyze(contexts)
            ai_issues = {result.vacancy_id: result.issues for result in batch.results}
            ai_failures = {failure.vacancy_id: failure.reason for failure in batch.failures}
        else:
            ai_state = "partial"
            logger.warning(
                "AI provider is not configured: only programmatic rules are applied",
                extra={"run_id": str(run)},
            )

        processed = 0
        failed = 0
        issues_total = 0

        for vacancy, rule_issues in candidates:
            analysis_id = await self._analyses.create(
                vacancy_id=vacancy.id,
                content_hash=vacancy.content_hash,
                provider=self._settings.ai_provider,
                model_name=self._settings.ai_model or None,
            )
            failure = ai_failures.get(vacancy.external_id)
            if failure:
                failed += 1
                logger.warning(
                    "vacancy analysis failed, programmatic rules are stored",
                    extra={"vacancy_id": vacancy.external_id, "reason": failure},
                )
                merged = self._verifier.verify(self._merger.merge(rule_issues, []), vacancy.normalized)
                await self._analyses.complete(analysis_id, merged, status="partial")
                processed += 1
                issues_total += len(merged)
                await self._cache.invalidate_vacancy(vacancy.external_id)
                continue

            merged = self._merger.merge(rule_issues, ai_issues.get(vacancy.external_id, []))
            merged = self._verifier.verify(merged, vacancy.normalized)
            await self._analyses.complete(analysis_id, merged, status=ai_state)
            processed += 1
            issues_total += len(merged)
            await self._cache.invalidate_vacancy(vacancy.external_id)

        status = self._run_status(processed, failed, ai_state)
        error_message = f"{failed} vacancy(ies) failed" if failed else None
        await self._runs.finish(run, status, processed, failed, error_message)
        logger.info(
            "analysis finished",
            extra={
                "run_id": str(run),
                "status": status,
                "processed": processed,
                "failed": failed,
                "issues": issues_total,
            },
        )
        return AnalysisResultDTO(
            run_id=run,
            status=status,
            processed_count=processed,
            failed_count=failed,
            issues_count=issues_total,
        )

    def _run_status(self, processed: int, failed: int, ai_state: str) -> str:
        if failed and not processed:
            return "failed"
        if failed or ai_state == "partial":
            return "partial"
        return "success"
