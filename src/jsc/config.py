"""Application configuration via environment variables."""

from urllib.parse import urlparse, urlunparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://jsc:devpassword@localhost:5432/jsc"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: list[str] = ["http://localhost:3000"]
    api_key: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_llm_model: str = "gpt-4o-mini"

    # Ingestion
    ingestion_rate_limit_delay: float = 1.0
    ingestion_max_concurrent: int = 3
    ingestion_playwright_enabled: bool = False

    # Search providers
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    # Search cache
    search_cache_query_ttl: int = 3600
    search_cache_job_ttl: int = 14400
    search_cache_max_queries: int = 1000
    search_cache_max_jobs: int = 5000

    # Ranking weights
    weight_semantic: float = 0.40
    weight_skill_coverage: float = 0.25
    weight_title_match: float = 0.15
    weight_seniority: float = 0.10
    weight_location: float = 0.10

    # Location
    target_locations: list[str] = ["Edmonton", "Calgary"]

    @model_validator(mode="after")
    def _validate_weights(self) -> "Settings":
        total = (
            self.weight_semantic
            + self.weight_skill_coverage
            + self.weight_title_match
            + self.weight_seniority
            + self.weight_location
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Ranking weights must sum to 1.0, got {total:.4f}")
        return self

    @property
    def database_url_sync(self) -> str:
        """Sync URL for Alembic (strips async driver from scheme)."""
        parsed = urlparse(self.database_url)
        scheme = parsed.scheme.split("+")[0]
        return urlunparse(parsed._replace(scheme=scheme))
