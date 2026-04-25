from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    database_url: str
    alembic_database_url: str

    redis_url: str
    celery_broker_url: str
    celery_result_backend: str

    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    dev_bypass_auth: bool = False

    anthropic_api_key: str = ""
    anthropic_model_opus: str = "claude-opus-4-7"
    anthropic_model_sonnet: str = "claude-sonnet-4-6"
    anthropic_model_haiku: str = "claude-haiku-4-5-20251001"

    sec_edgar_user_agent: str = "AlphaFolio Dev dev@example.com"
    tavily_api_key: str = ""
    polygon_stub_fixtures: str = "./tests/fixtures/polygon"
    quiver_stub_fixtures: str = "./tests/fixtures/quiver"

    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "alphafolio-dev"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
