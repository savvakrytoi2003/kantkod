from dishka import Provider, Scope, provide

from app.domain.use_cases.analyze_vacancies import AnalyzeVacanciesUseCase
from app.domain.use_cases.generate_report import GenerateReportUseCase
from app.domain.use_cases.generate_resume_draft import GenerateResumeDraftUseCase
from app.domain.use_cases.get_analysis_history import GetAnalysisHistoryUseCase
from app.domain.use_cases.get_report import GetReportUseCase
from app.domain.use_cases.get_run import GetRunUseCase
from app.domain.use_cases.get_run_history import GetRunHistoryUseCase
from app.domain.use_cases.get_sync_history import GetSyncHistoryUseCase
from app.domain.use_cases.get_sync_status import GetSyncStatusUseCase
from app.domain.use_cases.get_vacancy import GetVacancyUseCase
from app.domain.use_cases.get_vacancy_issues import GetVacancyIssuesUseCase
from app.domain.use_cases.list_issue_vacancies import ListIssueVacanciesUseCase
from app.domain.use_cases.list_vacancies import ListVacanciesUseCase
from app.domain.use_cases.retry_analysis import RetryAnalysisUseCase
from app.domain.use_cases.sync_vacancies import SyncVacanciesUseCase
from app.domain.use_cases.validate_json import ValidateJsonUseCase


class UseCaseProvider(Provider):
    scope = Scope.REQUEST

    sync_vacancies = provide(SyncVacanciesUseCase)
    analyze_vacancies = provide(AnalyzeVacanciesUseCase)
    retry_analysis = provide(RetryAnalysisUseCase)
    get_vacancy = provide(GetVacancyUseCase)
    get_vacancy_issues = provide(GetVacancyIssuesUseCase)
    list_vacancies = provide(ListVacanciesUseCase)
    list_issue_vacancies = provide(ListIssueVacanciesUseCase)
    generate_report = provide(GenerateReportUseCase)
    generate_resume_draft = provide(GenerateResumeDraftUseCase)
    get_report = provide(GetReportUseCase)
    validate_json = provide(ValidateJsonUseCase)
    get_analysis_history = provide(GetAnalysisHistoryUseCase)
    get_sync_history = provide(GetSyncHistoryUseCase)
    get_sync_status = provide(GetSyncStatusUseCase)
    get_run = provide(GetRunUseCase)
    get_run_history = provide(GetRunHistoryUseCase)
