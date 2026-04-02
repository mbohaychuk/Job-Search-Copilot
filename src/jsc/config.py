"""Application configuration via environment variables."""

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

    # OpenAI
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_llm_model: str = "gpt-4o-mini"

    # Ingestion
    ingestion_rate_limit_delay: float = 1.0
    ingestion_max_concurrent: int = 3
    ingestion_playwright_enabled: bool = False

    # Ranking weights
    weight_semantic: float = 0.40
    weight_skill_coverage: float = 0.25
    weight_title_match: float = 0.15
    weight_seniority: float = 0.10
    weight_location: float = 0.10

    # Location
    target_locations: list[str] = ["Edmonton", "Calgary"]

    @property
    def database_url_sync(self) -> str:
        """Sync URL for Alembic (replaces asyncpg with psycopg2)."""
        return self.database_url.replace("+asyncpg", "")
