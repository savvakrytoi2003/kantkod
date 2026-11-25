from app.infrastructure.database.models.analysis_run import AnalysisRunModel
from app.infrastructure.database.models.report_run import ReportRunModel
from app.infrastructure.database.models.sync_run import SyncRunModel
from app.infrastructure.database.models.vacancy import VacancyModel
from app.infrastructure.database.models.vacancy_issue import VacancyIssueModel
from app.schemas.api_response import AnalysisRunDTO, ReportRunDTO, SyncRunDTO
from app.schemas.issue import IssueDTO, IssueTopic
from app.schemas.vacancy import NormalizedVacancyDTO, StoredVacancyDTO


def vacancy_to_dto(model: VacancyModel) -> StoredVacancyDTO:
    return StoredVacancyDTO(
        id=model.id,
        external_id=model.external_id,
        source_url=model.source_url,
        title=model.title,
        description=model.description,
        normalized=NormalizedVacancyDTO.model_validate(model.normalized_data),
        content_hash=model.content_hash,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
        last_synced_at=model.last_synced_at,
    )


def issue_to_dto(model: VacancyIssueModel) -> IssueDTO:
    return IssueDTO(
        topic=IssueTopic(model.topic),
        source_field=model.source_field,
        quote=model.quote,
        problem=model.problem,
        recommendation=model.recommendation,
    )


def sync_run_to_dto(model: SyncRunModel) -> SyncRunDTO:
    return SyncRunDTO(
        id=model.id,
        status=model.status,
        started_at=model.started_at,
        finished_at=model.finished_at,
        received_count=model.received_count,
        created_count=model.created_count,
        updated_count=model.updated_count,
        unchanged_count=model.unchanged_count,
        failed_count=model.failed_count,
        error_message=model.error_message,
    )


def analysis_run_to_dto(model: AnalysisRunModel) -> AnalysisRunDTO:
    return AnalysisRunDTO(
        id=model.id,
        status=model.status,
        started_at=model.started_at,
        finished_at=model.finished_at,
        processed_count=model.processed_count,
        failed_count=model.failed_count,
        provider=model.provider,
        model_name=model.model_name,
        error_message=model.error_message,
    )


def report_run_to_dto(model: ReportRunModel) -> ReportRunDTO:
    return ReportRunDTO(
        id=model.id,
        status=model.status,
        created_at=model.created_at,
        completed_at=model.completed_at,
        report_path=model.report_path,
        vacancies_count=model.vacancies_count,
        issues_count=model.issues_count,
        error_message=model.error_message,
    )
