import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dishka import make_async_container
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from app.config.logging import configure_logging
from app.config.settings import Settings
from app.di.providers import PROVIDERS
from app.infrastructure.jobs.job_runner import JobRunner
from app.infrastructure.scheduler.scheduler_service import SchedulerService
from app.presentation.api.exception_handlers import register_exception_handlers
from app.presentation.api.router import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler: SchedulerService = app.state.scheduler
    scheduler.start()
    logger.info("application started", extra={"env": app.state.settings.app_env})
    try:
        yield
    finally:
        scheduler.shutdown()
        await app.state.container.close()
        logger.info("application stopped")


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging("DEBUG" if settings.app_env == "development" else "INFO")

    container = make_async_container(*PROVIDERS)

    app = FastAPI(title="KantKod", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.container = container
    app.state.job_runner = JobRunner(container)
    app.state.scheduler = SchedulerService(container, settings)

    setup_dishka(container, app)
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
