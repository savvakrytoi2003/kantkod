from dishka import Provider, Scope, provide

from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.database.repositories.analysis_run_repository import AnalysisRunRepository
from app.infrastructure.database.repositories.report_run_repository import ReportRunRepository
from app.infrastructure.database.repositories.sync_run_repository import SyncRunRepository
from app.infrastructure.database.repositories.vacancy_repository import VacancyRepository


class RepositoryProvider(Provider):
    scope = Scope.REQUEST

    vacancy_repository = provide(VacancyRepository)
    analysis_repository = provide(AnalysisRepository)
    sync_run_repository = provide(SyncRunRepository)
    analysis_run_repository = provide(AnalysisRunRepository)
    report_run_repository = provide(ReportRunRepository)
