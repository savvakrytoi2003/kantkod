from app.infrastructure.database.repositories.sync_run_repository import SyncRunRepository
from app.schemas.api_response import SyncStatusDTO


class GetSyncStatusUseCase:
    """Returns the latest synchronization run."""

    def __init__(self, sync_run_repository: SyncRunRepository) -> None:
        self._runs = sync_run_repository

    async def execute(self) -> SyncStatusDTO:
        return SyncStatusDTO(latest_run=await self._runs.latest())
