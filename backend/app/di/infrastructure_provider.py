from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, provide
from redis.asyncio import Redis

from app.config.settings import Settings
from app.domain.services.ai_context_builder import AiContextBuilder
from app.domain.services.ai_prompt_builder import AiPromptBuilder
from app.domain.services.ai_response_validator import AiResponseValidator
from app.domain.services.content_hasher import ContentHasher
from app.domain.services.issue_merger import IssueMerger
from app.domain.services.report_builder import ReportBuilder
from app.domain.services.resume_prompt_builder import ResumePromptBuilder
from app.domain.services.resume_response_validator import ResumeResponseValidator
from app.domain.services.rule_checker import RuleChecker
from app.domain.services.source_payload_parser import SourcePayloadParser
from app.domain.services.vacancy_normalizer import VacancyNormalizer
from app.infrastructure.ai.batch_vacancy_analyzer import BatchVacancyAnalyzer
from app.infrastructure.ai.openai_compatible_client import OpenAiCompatibleClient
from app.infrastructure.api.trudvsem_client import TrudvsemClient
from app.infrastructure.cache.redis_vacancy_cache import RedisVacancyCache
from app.infrastructure.reports.report_writer import ReportWriter


class InfrastructureProvider(Provider):
    scope = Scope.APP

    @provide
    async def http_client(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            yield client

    @provide
    async def redis_client(self, settings: Settings) -> AsyncIterator[Redis]:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()

    parser = provide(SourcePayloadParser)
    normalizer = provide(VacancyNormalizer)
    hasher = provide(ContentHasher)
    rule_checker = provide(RuleChecker)
    issue_merger = provide(IssueMerger)
    report_builder = provide(ReportBuilder)
    context_builder = provide(AiContextBuilder)
    prompt_builder = provide(AiPromptBuilder)
    response_validator = provide(AiResponseValidator)
    resume_prompt_builder = provide(ResumePromptBuilder)
    resume_response_validator = provide(ResumeResponseValidator)
    report_writer = provide(ReportWriter)

    @provide
    def source_client(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        parser: SourcePayloadParser,
    ) -> TrudvsemClient:
        return TrudvsemClient(settings=settings, client=client, parser=parser)

    @provide
    def cache(self, client: Redis, settings: Settings) -> RedisVacancyCache:
        return RedisVacancyCache(client=client, settings=settings)

    @provide
    def ai_client(self, settings: Settings, client: httpx.AsyncClient) -> OpenAiCompatibleClient:
        return OpenAiCompatibleClient(settings=settings, client=client)

    @provide
    def ai_analyzer(
        self,
        settings: Settings,
        client: OpenAiCompatibleClient,
        prompt_builder: AiPromptBuilder,
        validator: AiResponseValidator,
    ) -> BatchVacancyAnalyzer:
        return BatchVacancyAnalyzer(
            settings=settings,
            client=client,
            prompt_builder=prompt_builder,
            validator=validator,
        )
