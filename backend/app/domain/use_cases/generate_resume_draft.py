import logging

from app.config.settings import Settings
from app.domain.errors import (
    AiNotConfiguredError,
    AiResponseInvalidError,
    InvalidResumeError,
    VacancyNotFoundError,
)
from app.domain.services.resume_prompt_builder import ResumePromptBuilder
from app.domain.services.resume_response_validator import ResumeResponseValidator
from app.infrastructure.ai.openai_compatible_client import OpenAiCompatibleClient
from app.infrastructure.database.repositories.vacancy_repository import VacancyRepository
from app.schemas.resume import ResumeDraftDTO, ResumeDraftRequestDTO, ResumeDTO

logger = logging.getLogger(__name__)


class GenerateResumeDraftUseCase:
    """Собирает черновик резюме под выбранную вакансию, не сохраняя резюме."""

    def __init__(
        self,
        settings: Settings,
        vacancy_repository: VacancyRepository,
        ai_client: OpenAiCompatibleClient,
        prompt_builder: ResumePromptBuilder,
        validator: ResumeResponseValidator,
    ) -> None:
        self._settings = settings
        self._vacancies = vacancy_repository
        self._ai = ai_client
        self._prompt = prompt_builder
        self._validator = validator

    async def execute(self, request: ResumeDraftRequestDTO) -> ResumeDraftDTO:
        vacancy = await self._vacancies.get_by_external_id(request.vacancy_id)
        if vacancy is None:
            raise VacancyNotFoundError(f"Vacancy {request.vacancy_id} is not found")

        resume = request.resume if isinstance(request.resume, ResumeDTO) else ResumeDTO(text=request.resume)
        if not self._has_content(resume):
            raise InvalidResumeError("Resume is empty: add text, experience, skills or education")

        if not self._settings.ai_configured:
            raise AiNotConfiguredError("AI provider is not configured: set AI_API_KEY, AI_BASE_URL and AI_MODEL")

        system = self._prompt.system_prompt()
        user = self._prompt.user_prompt(vacancy.normalized, resume)
        logger.info("resume draft requested", extra={"vacancy_id": vacancy.external_id})
        raw = await self._ai.complete_json(system, user)
        try:
            content = self._validator.validate(raw)
        except AiResponseInvalidError:
            logger.warning("resume draft response is invalid, asking for a repair")
            repaired = await self._ai.complete_json(system, user + "\n\n" + self._prompt.repair_prompt(str(raw)))
            content = self._validator.validate(repaired)

        return ResumeDraftDTO(
            vacancy_id=vacancy.external_id,
            vacancy_title=vacancy.title,
            company_name=vacancy.normalized.company_name,
            source_url=vacancy.source_url,
            summary=content.summary,
            highlighted_skills=content.highlighted_skills,
            experience_highlights=content.experience_highlights,
            education_highlights=content.education_highlights,
            gaps=content.gaps,
            draft_text=content.draft_text,
            notes=[
                "Черновик собран только по вашему резюме. Проверьте факты, даты и формулировки перед отправкой.",
                "Резюме не сохраняется на сервере.",
            ],
        )

    def _has_content(self, resume: ResumeDTO) -> bool:
        if len(resume.text.strip()) >= 20:
            return True
        return any(
            [
                resume.summary.strip(),
                resume.target_position.strip(),
                resume.experience,
                resume.education,
                resume.skills,
                resume.certificates,
                resume.languages,
            ],
        )
