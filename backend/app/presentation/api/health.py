import logging

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.cache.redis_vacancy_cache import RedisVacancyCache
from app.schemas.api_response import HealthDTO

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthDTO)
@inject
async def health(
    request: Request,
    session: FromDishka[AsyncSession],
    cache: FromDishka[RedisVacancyCache],
) -> HealthDTO:
    database = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        database = "unavailable"
        logger.error("database health check failed", extra={"error": str(exc)})

    redis_status = "ok" if await cache.ping() else "unavailable"
    scheduler = request.app.state.scheduler
    return HealthDTO(
        status="ok" if database == "ok" and redis_status == "ok" else "degraded",
        version=request.app.version,
        database=database,
        redis=redis_status,
        scheduler="running" if scheduler and scheduler.running else "stopped",
    )
