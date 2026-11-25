import uuid
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.vacancy import VacancyCandidate
from app.infrastructure.database.mappers import issue_to_dto, vacancy_to_dto
from app.infrastructure.database.models.vacancy import VacancyModel
from app.infrastructure.database.models.vacancy_analysis import VacancyAnalysisModel
from app.infrastructure.database.models.vacancy_issue import VacancyIssueModel
from app.schemas.vacancy import StoredVacancyDTO, VacancyWithIssuesDTO

FINISHED_ANALYSIS_STATUSES = ("success", "partial")


class VacancyRepository:
    """Persistence for vacancies."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_external_id(self, external_id: str) -> StoredVacancyDTO | None:
        stmt = select(VacancyModel).where(VacancyModel.external_id == external_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return vacancy_to_dto(model) if model else None

    async def create(self, candidate: VacancyCandidate, synced_at: datetime) -> StoredVacancyDTO:
        model = VacancyModel(
            external_id=candidate.external_id,
            source_url=candidate.normalized.source_url,
            title=candidate.normalized.title,
            description=candidate.normalized.description,
            normalized_data=candidate.normalized.model_dump(mode="json"),
            raw_data=candidate.raw,
            content_hash=candidate.content_hash,
            is_active=True,
            last_synced_at=synced_at,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return vacancy_to_dto(model)

    async def update(
        self,
        vacancy_id: uuid.UUID,
        candidate: VacancyCandidate,
        synced_at: datetime,
    ) -> StoredVacancyDTO:
        model = await self._session.get(VacancyModel, vacancy_id)
        if model is None:
            raise ValueError(f"Vacancy {vacancy_id} disappeared during update")
        model.source_url = candidate.normalized.source_url
        model.title = candidate.normalized.title
        model.description = candidate.normalized.description
        model.normalized_data = candidate.normalized.model_dump(mode="json")
        model.raw_data = candidate.raw
        model.content_hash = candidate.content_hash
        model.is_active = True
        model.last_synced_at = synced_at
        await self._session.commit()
        await self._session.refresh(model)
        return vacancy_to_dto(model)

    async def list_page(self, limit: int, offset: int) -> list[StoredVacancyDTO]:
        stmt = select(VacancyModel).order_by(VacancyModel.updated_at.desc()).limit(limit).offset(offset)
        models = (await self._session.execute(stmt)).scalars().all()
        return [vacancy_to_dto(model) for model in models]

    async def count(self) -> int:
        stmt = select(func.count()).select_from(VacancyModel)
        return int((await self._session.execute(stmt)).scalar_one())

    async def list_pending_analysis(
        self,
        limit: int,
        include_analyzed: bool = False,
    ) -> list[StoredVacancyDTO]:
        stmt = select(VacancyModel).order_by(VacancyModel.updated_at.asc()).limit(limit)
        if not include_analyzed:
            success_exists = exists().where(
                VacancyAnalysisModel.vacancy_id == VacancyModel.id,
                VacancyAnalysisModel.content_hash == VacancyModel.content_hash,
                VacancyAnalysisModel.status == "success",
            )
            stmt = stmt.where(~success_exists)
        models = (await self._session.execute(stmt)).scalars().all()
        return [vacancy_to_dto(model) for model in models]

    async def list_with_issues(self, limit: int = 10000) -> list[VacancyWithIssuesDTO]:
        vacancies = (
            (await self._session.execute(select(VacancyModel).order_by(VacancyModel.external_id).limit(limit)))
            .scalars()
            .all()
        )
        if not vacancies:
            return []

        analysis_rows = (
            await self._session.execute(
                select(VacancyAnalysisModel.vacancy_id, VacancyAnalysisModel.id)
                .where(VacancyAnalysisModel.status.in_(FINISHED_ANALYSIS_STATUSES))
                .order_by(VacancyAnalysisModel.created_at, VacancyAnalysisModel.id),
            )
        ).all()
        latest_analysis: dict[uuid.UUID, uuid.UUID] = {}
        for vacancy_id, analysis_id in analysis_rows:
            latest_analysis[vacancy_id] = analysis_id

        issues_by_analysis: dict[uuid.UUID, list] = {}
        if latest_analysis:
            issue_models = (
                (
                    await self._session.execute(
                        select(VacancyIssueModel)
                        .where(VacancyIssueModel.analysis_id.in_(list(latest_analysis.values())))
                        .order_by(VacancyIssueModel.created_at),
                    )
                )
                .scalars()
                .all()
            )
            for issue_model in issue_models:
                issues_by_analysis.setdefault(issue_model.analysis_id, []).append(issue_to_dto(issue_model))

        result: list[VacancyWithIssuesDTO] = []
        for model in vacancies:
            analysis_id = latest_analysis.get(model.id)
            issues = issues_by_analysis.get(analysis_id, []) if analysis_id else []
            result.append(VacancyWithIssuesDTO(vacancy=vacancy_to_dto(model), issues=issues))
        return result
