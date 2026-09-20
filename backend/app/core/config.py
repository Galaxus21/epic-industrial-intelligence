"""
EPIC — Application Configuration
Loads settings from environment variables with sensible defaults.
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"
    llm_provider: str = "openai"
    embedding_provider: str = "openai"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # PostgreSQL
    database_url: str = "sqlite+aiosqlite:///./epic.db"

    # App
    environment: str = "development"

    # Security
    auth_provider: str = "local"
    # HMAC key for auth tokens. MUST be overridden in production — startup fails otherwise.
    secret_key: str = "dev-insecure-secret-change-me"

    # Data governance
    # When False (default) document ingestion never auto-creates equipment or other
    # master-data records — extracted entities are held on the document for review.
    auto_register_entities: bool = False

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:3000",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
