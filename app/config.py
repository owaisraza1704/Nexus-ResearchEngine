from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration shared by the API and migrations."""

    environment: str = "development"
    database_url: str = "postgresql+psycopg://nexus:nexus@localhost:5432/nexus"
    artifact_store_path: Path = Path(".data/artifacts")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NEXUS_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
