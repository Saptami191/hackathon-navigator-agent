from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Hackathon Navigator"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = Field(..., min_length=32)
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Database
    database_url: PostgresDsn = Field(...)
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: RedisDsn = Field(...)
    redis_celery_db: int = 0
    redis_cache_db: int = 1

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "hackathon_navigator"

    # AI
    anthropic_api_key: str = Field(...)
    openai_api_key: str = Field(...)
    claude_model: str = "claude-sonnet-4-6"
    gpt_model: str = "gpt-4.1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # GitHub
    github_token: str = Field(...)
    github_webhook_secret: str = Field(...)

    # Clerk (Auth)
    clerk_secret_key: str = Field(...)
    clerk_publishable_key: str = Field(...)
    clerk_jwt_verification_key: str = Field(...)

    # Agent settings
    max_agent_iterations: int = 10
    agent_timeout_seconds: int = 120
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    rag_top_k: int = 8

    # Celery
    celery_task_serializer: str = "json"
    celery_result_backend_transport_options: dict = {}

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()