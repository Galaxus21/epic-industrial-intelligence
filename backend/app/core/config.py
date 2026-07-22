"""
AI Operations Brain — Application Configuration
Loads settings from environment variables with sensible defaults.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "opsbrain2024"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # PostgreSQL
    database_url: str = "sqlite+aiosqlite:///./opsbrain.db"

    # Azure Document Intelligence (optional)
    azure_doc_intel_endpoint: str = ""
    azure_doc_intel_key: str = ""

    # App
    environment: str = "development"
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
