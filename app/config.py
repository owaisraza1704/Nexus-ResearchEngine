from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration shared by the API and migrations."""

    environment: str = "development"
    database_url: str = "postgresql+psycopg://nexus:nexus@localhost:5432/nexus"
    artifact_store_path: Path = Path(".data/artifacts")
    max_upload_bytes: int = 20 * 1024 * 1024
    max_document_pages: int = 100
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str | None = None
    azure_openai_embedding_deployment: str | None = None
    azure_openai_embedding_dimensions: int = 3072

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NEXUS_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
