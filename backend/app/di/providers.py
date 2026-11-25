from app.di.config_provider import ConfigProvider
from app.di.database_provider import DatabaseProvider
from app.di.infrastructure_provider import InfrastructureProvider
from app.di.repository_provider import RepositoryProvider
from app.di.use_case_provider import UseCaseProvider

PROVIDERS = (
    ConfigProvider(),
    DatabaseProvider(),
    InfrastructureProvider(),
    RepositoryProvider(),
    UseCaseProvider(),
)
