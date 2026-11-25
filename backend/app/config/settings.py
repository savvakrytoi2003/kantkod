from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "postgresql+asyncpg://kantkod:kantkod@localhost:5432/kantkod"
    redis_url: str = "redis://localhost:6379/0"

    source_api_url: str = "http://opendata.trudvsem.ru/api/v1/vacancies/region/39"
    source_region: int = 39
    source_max_vacancies: int = 500
    source_page_size: int = 100
    source_timeout: float = 30.0
    source_max_retries: int = 3

    sync_interval_minutes: int = 60
    scheduler_enabled: bool = True

    ai_provider: str = "openai_compatible"
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_thinking: bool = True
    ai_batch_size: int = 20
    ai_max_concurrency: int = 3
    ai_timeout: float = 120.0
    ai_max_retries: int = 3
    ai_enabled: bool = True

    reports_dir: str = "reports"
    cache_ttl_seconds: int = 600

    @property
    def ai_configured(self) -> bool:
        return bool(self.ai_enabled and self.ai_base_url and self.ai_api_key and self.ai_model)
