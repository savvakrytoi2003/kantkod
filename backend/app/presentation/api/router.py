from fastapi import APIRouter

from app.presentation.api import (
    analysis,
    health,
    reports,
    resume,
    runs,
    synchronization,
    vacancies,
    validation,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(vacancies.router, prefix="/api/v1")
api_router.include_router(synchronization.router, prefix="/api/v1")
api_router.include_router(analysis.router, prefix="/api/v1")
api_router.include_router(reports.router, prefix="/api/v1")
api_router.include_router(validation.router, prefix="/api/v1")
api_router.include_router(resume.router, prefix="/api/v1")
api_router.include_router(runs.router, prefix="/api/v1")
