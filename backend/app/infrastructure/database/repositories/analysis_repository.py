import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.clock import utcnow
from app.infrastructure.database.mappers import issue_to_dto
from app.infrastructure.database.models.vacancy_analysis import VacancyAnalysisModel
from app.infrastructure.database.models.vacancy_issue import VacancyIssueModel
from app.schemas.issue import IssueDTO


class AnalysisRepository:
    """Persistence for vacancy analyses and their issues."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        vacancy_id: uuid.UUID,
        content_hash: str,
        provider: str | None,
        model_name: str | None,
    ) -> uuid.UUID:
        model = VacancyAnalysisModel(
            vacancy_id=vacancy_id,
            content_hash=content_hash,
            provider=provider,
            model_name=model_name,
            status="running",
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return model.id

    async def complete(self, analysis_id: uuid.UUID, issues: list[IssueDTO], status: str = "success") -> None:
        model = await self._session.get(VacancyAnalysisModel, analysis_id)
        if model is None:
            return
        for issue in issues:
            self._session.add(
                VacancyIssueModel(
                    analysis_id=analysis_id,
                    topic=str(issue.topic),
                    source_field=issue.source_field,
                    quote=issue.quote,
                    problem=issue.problem,
                    recommendation=issue.recommendation,
                ),
            )
        model.status = status
        model.completed_at = utcnow()
        await self._session.commit()

    async def fail(self, analysis_id: uuid.UUID, error_message: str) -> None:
        model = await self._session.get(VacancyAnalysisModel, analysis_id)
        if model is None:
            return
        model.status = "failed"
        model.completed_at = utcnow()
        model.error_message = error_message[:2000]
        await self._session.commit()

    async def has_success(self, vacancy_id: uuid.UUID, content_hash: str) -> bool:
        stmt = select(VacancyAnalysisModel.id).where(
            VacancyAnalysisModel.vacancy_id == vacancy_id,
            VacancyAnalysisModel.content_hash == content_hash,
            VacancyAnalysisModel.status == "success",
        )
        return (await self._session.execute(stmt)).first() is not None

    async def latest_success_id(self, vacancy_id: uuid.UUID) -> uuid.UUID | None:
        stmt = (
            select(VacancyAnalysisModel.id)
            .where(
                VacancyAnalysisModel.vacancy_id == vacancy_id,
                VacancyAnalysisModel.status == "success",
            )
            .order_by(VacancyAnalysisModel.completed_at.desc(), VacancyAnalysisModel.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def latest_issues(self, vacancy_id: uuid.UUID) -> list[IssueDTO]:
        analysis_id = await self.latest_success_id(vacancy_id)
        if analysis_id is None:
            return []
        stmt = (
            select(VacancyIssueModel)
            .where(VacancyIssueModel.analysis_id == analysis_id)
            .order_by(VacancyIssueModel.created_at)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [issue_to_dto(model) for model in models]
