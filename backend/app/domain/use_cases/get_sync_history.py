from app.infrastructure.database.repositories.sync_run_repository import SyncRunRepository
from app.schemas.api_response import SyncRunDTO


class GetSyncHistoryUseCase:
    """Returns the history of synchronization runs."""

    def __init__(self, sync_run_repository: SyncRunRepository) -> None:
        self._runs = sync_run_repository

    async def execute(self, limit: int = 50) -> list[SyncRunDTO]:
        return await self._runs.list(limit)
