import asyncio
import json
import logging

from app.config.settings import Settings
from app.domain.errors import (
    AiClientError,
    AiContextLengthError,
    AiNotConfiguredError,
    AiResponseInvalidError,
)
from app.domain.services.ai_prompt_builder import AiPromptBuilder
from app.domain.services.ai_response_validator import AiResponseValidator
from app.infrastructure.ai.openai_compatible_client import OpenAiCompatibleClient
from app.schemas.analysis import (
    AiVacancyContextDTO,
    BatchAnalysisResultDTO,
    BatchFailureDTO,
)

logger = logging.getLogger(__name__)


class BatchVacancyAnalyzer:
    """Splits vacancies into batches, calls the AI provider and validates answers."""

    def __init__(
        self,
        settings: Settings,
        client: OpenAiCompatibleClient,
        prompt_builder: AiPromptBuilder,
        validator: AiResponseValidator,
    ) -> None:
        self._settings = settings
        self._client = client
        self._prompt_builder = prompt_builder
        self._validator = validator

    async def analyze(self, contexts: list[AiVacancyContextDTO]) -> BatchAnalysisResultDTO:
        if not contexts:
            return BatchAnalysisResultDTO()

        batch_size = max(1, self._settings.ai_batch_size)
        concurrency = max(1, self._settings.ai_max_concurrency)
        chunks = [contexts[index:index + batch_size] for index in range(0, len(contexts), batch_size)]
        logger.info("ai batches prepared", extra={"vacancies": len(contexts), "batches": len(chunks)})

        semaphore = asyncio.Semaphore(concurrency)

        async def run(chunk: list[AiVacancyContextDTO]) -> tuple[list, list[BatchFailureDTO]]:
            async with semaphore:
                return await self._analyze_chunk(chunk)

        outcomes = await asyncio.gather(*(run(chunk) for chunk in chunks))

        results = [item for chunk_results, _ in outcomes for item in chunk_results]
        failures = [failure for _, chunk_failures in outcomes for failure in chunk_failures]
        logger.info(
            "ai batches finished",
            extra={"results": len(results), "failures": len(failures), "batches": len(chunks)},
        )
        return BatchAnalysisResultDTO(results=results, failures=failures)

    async def _analyze_chunk(
        self,
        chunk: list[AiVacancyContextDTO],
    ) -> tuple[list, list[BatchFailureDTO]]:
        requested = {context.vacancy_id for context in chunk}
        user_prompt = self._prompt_builder.user_prompt(chunk)
        system_prompt = self._prompt_builder.system_prompt()

        try:
            raw = await self._client.complete_json(system_prompt, user_prompt)
            try:
                validated, missing = self._validator.validate(self._parse(raw), requested)
            except AiResponseInvalidError:
                logger.warning("ai response is invalid, asking for a repair", extra={"size": len(chunk)})
                repaired = await self._client.complete_json(
                    system_prompt,
                    user_prompt + "\n\n" + self._prompt_builder.repair_prompt(raw),
                )
                validated, missing = self._validator.validate(self._parse(repaired), requested)
        except AiContextLengthError as exc:
            if len(chunk) > 1:
                return await self._split_and_retry(chunk)
            return [], self._fail_all(chunk, f"{type(exc).__name__}: {exc}")
        except (AiClientError, AiNotConfiguredError, AiResponseInvalidError) as exc:
            return [], self._fail_all(chunk, f"{type(exc).__name__}: {exc}")

        if missing and len(chunk) > 1:
            retried, not_found = await self._retry_individually(chunk, missing)
            return validated + retried, not_found

        failures = [
            BatchFailureDTO(vacancy_id=vacancy_id, reason="AI response does not contain this vacancy")
            for vacancy_id in missing
        ]
        return validated, failures

    async def _retry_individually(
        self,
        chunk: list[AiVacancyContextDTO],
        missing: list[str],
    ) -> tuple[list, list[BatchFailureDTO]]:
        """Повторяет запрос по одной вакансии: модель иногда теряет часть батча."""
        by_id = {context.vacancy_id: context for context in chunk}
        logger.info("ai missing vacancies retried individually", extra={"count": len(missing)})
        results: list = []
        failures: list[BatchFailureDTO] = []
        for vacancy_id in missing:
            context = by_id.get(vacancy_id)
            if context is None:
                continue
            retried, retried_failures = await self._analyze_chunk([context])
            if retried:
                results.extend(retried)
            else:
                failures.extend(retried_failures)
        return results, failures

    async def _split_and_retry(
        self,
        chunk: list[AiVacancyContextDTO],
    ) -> tuple[list, list[BatchFailureDTO]]:
        middle = len(chunk) // 2
        left = await self._analyze_chunk(chunk[:middle])
        right = await self._analyze_chunk(chunk[middle:])
        return left[0] + right[0], left[1] + right[1]

    def _fail_all(self, chunk: list[AiVacancyContextDTO], reason: str) -> list[BatchFailureDTO]:
        return [BatchFailureDTO(vacancy_id=context.vacancy_id, reason=reason[:500]) for context in chunk]

    def _parse(self, raw: str) -> dict | list:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        start = min(
            (index for index in (text.find("{"), text.find("[")) if index != -1),
            default=-1,
        )
        if start > 0:
            text = text[start:]
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AiResponseInvalidError(f"AI response is not valid JSON: {exc}") from exc
