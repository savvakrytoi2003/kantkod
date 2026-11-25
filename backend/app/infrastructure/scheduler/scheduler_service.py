import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dishka import AsyncContainer

from app.config.settings import Settings
from app.infrastructure.jobs.job_runner import JobRunner

logger = logging.getLogger(__name__)


class SchedulerService:
    """APScheduler wrapper that runs the synchronization cycle on an interval."""

    _JOB_ID = "sync-cycle"

    def __init__(self, container: AsyncContainer, settings: Settings) -> None:
        self._settings = settings
        self._runner = JobRunner(container)
        self._scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self) -> None:
        if not self._settings.scheduler_enabled:
            logger.info("scheduler is disabled")
            return
        self._scheduler.add_job(
            self._runner.run_cycle,
            trigger="interval",
            minutes=self._settings.sync_interval_minutes,
            id=self._JOB_ID,
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(
            "scheduler started",
            extra={"interval_minutes": self._settings.sync_interval_minutes},
        )

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("scheduler stopped")

    @property
    def running(self) -> bool:
        return bool(self._scheduler.running)
