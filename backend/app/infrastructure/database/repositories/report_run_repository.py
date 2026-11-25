import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.clock import utcnow
from app.infrastructure.database.mappers import report_run_to_dto
from app.infrastructure.database.models.report_run import ReportRunModel
from app.schemas.api_response import ReportRunDTO


class ReportRunRepository:
    """History of report generation runs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start(self, status: str = "running") -> uuid.UUID:
        model = ReportRunModel(status=status)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return model.id

    async def finish(
        self,
        run_id: uuid.UUID,
        status: str,
        report_path: str | None = None,
        vacancies_count: int = 0,
        issues_count: int = 0,
        error_message: str | None = None,
    ) -> ReportRunDTO | None:
        model = await self._session.get(ReportRunModel, run_id)
        if model is None:
            return None
        model.status = status
        model.completed_at = utcnow()
        model.report_path = report_path
        model.vacancies_count = vacancies_count
        model.issues_count = issues_count
        model.error_message = error_message[:2000] if error_message else None
        await self._session.commit()
        await self._session.refresh(model)
        return report_run_to_dto(model)

    async def get(self, run_id: uuid.UUID) -> ReportRunDTO | None:
        model = await self._session.get(ReportRunModel, run_id)
        return report_run_to_dto(model) if model else None

    async def latest_success(self) -> ReportRunDTO | None:
        stmt = (
            select(ReportRunModel)
            .where(ReportRunModel.status == "success")
            .order_by(ReportRunModel.completed_at.desc())
            .limit(1)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return report_run_to_dto(model) if model else None

    async def list(self, limit: int = 50) -> list[ReportRunDTO]:
        stmt = select(ReportRunModel).order_by(ReportRunModel.created_at.desc()).limit(limit)
        models = (await self._session.execute(stmt)).scalars().all()
        return [report_run_to_dto(model) for model in models]
