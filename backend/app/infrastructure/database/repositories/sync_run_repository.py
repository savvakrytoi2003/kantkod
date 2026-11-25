import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.clock import utcnow
from app.infrastructure.database.mappers import sync_run_to_dto
from app.infrastructure.database.models.sync_run import SyncRunModel
from app.schemas.api_response import SyncRunDTO


class SyncRunRepository:
    """History of synchronization runs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start(self, status: str = "pending") -> SyncRunDTO:
        model = SyncRunModel(status=status)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return sync_run_to_dto(model)

    async def finish(
        self,
        run_id: uuid.UUID,
        status: str,
        received: int,
        created: int,
        updated: int,
        unchanged: int,
        failed: int,
        error_message: str | None = None,
    ) -> SyncRunDTO | None:
        model = await self._session.get(SyncRunModel, run_id)
        if model is None:
            return None
        model.status = status
        model.finished_at = utcnow()
        model.received_count = received
        model.created_count = created
        model.updated_count = updated
        model.unchanged_count = unchanged
        model.failed_count = failed
        model.error_message = error_message[:2000] if error_message else None
        await self._session.commit()
        await self._session.refresh(model)
        return sync_run_to_dto(model)

    async def get(self, run_id: uuid.UUID) -> SyncRunDTO | None:
        model = await self._session.get(SyncRunModel, run_id)
        return sync_run_to_dto(model) if model else None

    async def latest(self) -> SyncRunDTO | None:
        stmt = select(SyncRunModel).order_by(SyncRunModel.started_at.desc()).limit(1)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return sync_run_to_dto(model) if model else None

    async def list(self, limit: int = 50) -> list[SyncRunDTO]:
        stmt = select(SyncRunModel).order_by(SyncRunModel.started_at.desc()).limit(limit)
        models = (await self._session.execute(stmt)).scalars().all()
        return [sync_run_to_dto(model) for model in models]
