import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.clock import utcnow
from app.infrastructure.database.mappers import analysis_run_to_dto
from app.infrastructure.database.models.analysis_run import AnalysisRunModel
from app.schemas.api_response import AnalysisRunDTO


class AnalysisRunRepository:
    """History of analysis runs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start(
        self,
        provider: str | None,
        model_name: str | None,
        status: str = "pending",
    ) -> AnalysisRunDTO:
        model = AnalysisRunModel(status=status, provider=provider, model_name=model_name)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return analysis_run_to_dto(model)

    async def finish(
        self,
        run_id: uuid.UUID,
        status: str,
        processed: int,
        failed: int,
        error_message: str | None = None,
    ) -> AnalysisRunDTO | None:
        model = await self._session.get(AnalysisRunModel, run_id)
        if model is None:
            return None
        model.status = status
        model.finished_at = utcnow()
        model.processed_count = processed
        model.failed_count = failed
        model.error_message = error_message[:2000] if error_message else None
        await self._session.commit()
        await self._session.refresh(model)
        return analysis_run_to_dto(model)

    async def get(self, run_id: uuid.UUID) -> AnalysisRunDTO | None:
        model = await self._session.get(AnalysisRunModel, run_id)
        return analysis_run_to_dto(model) if model else None

    async def list(self, limit: int = 50) -> list[AnalysisRunDTO]:
        stmt = select(AnalysisRunModel).order_by(AnalysisRunModel.started_at.desc()).limit(limit)
        models = (await self._session.execute(stmt)).scalars().all()
        return [analysis_run_to_dto(model) for model in models]
