from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration shared by the API and migrations."""

    environment: str = "development"
    database_url: str = "postgresql+psycopg://nexus:nexus@localhost:5432/nexus"
    artifact_store_path: Path = Path(".data/artifacts")
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, ge=1)
    max_document_pages: int = Field(default=100, ge=1)
    max_document_chars: int = Field(default=500_000, ge=1)
    max_document_chunks: int = Field(default=1_000, ge=1)
    max_chunk_chars: int = Field(default=16_000, ge=1)
    max_question_chars: int = Field(default=4_000, ge=1)
    max_top_k: int = Field(default=20, ge=1)
    max_context_chars: int = Field(default=24_000, ge=1)
    max_answer_chars: int = Field(default=12_000, ge=1)
    max_answer_tokens: int = Field(default=2_000, ge=1)
    provider_timeout_seconds: float = Field(default=45.0, gt=0)
    answer_timeout_seconds: float = Field(default=90.0, gt=0)
    ingestion_timeout_seconds: float = Field(default=180.0, gt=0)
    max_research_sources: int = Field(default=5, ge=2)
    max_research_context_chars: int = Field(default=48_000, ge=1)
    max_research_evidence: int = Field(default=20, ge=1)
    max_research_claims: int = Field(default=12, ge=1)
    max_research_output_chars: int = Field(default=24_000, ge=1)
    max_research_output_tokens: int = Field(default=6_000, ge=1)
    research_timeout_seconds: float = Field(default=120.0, gt=0)
    worker_concurrency: int = Field(default=2, ge=1, le=8)
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_queue: str = "nexus"
    max_job_tasks: int = Field(default=12, ge=4, le=30)
    max_job_depth: int = Field(default=6, ge=3, le=10)
    max_job_parallel_tasks: int = Field(default=2, ge=1, le=8)
    max_job_provider_calls: int = Field(default=20, ge=2, le=100)
    max_job_input_tokens: int = Field(default=100_000, ge=1)
    max_job_output_tokens: int = Field(default=20_000, ge=1)
    job_timeout_seconds: int = Field(default=600, ge=10, le=3600)
    max_web_sources: int = Field(default=3, ge=0, le=5)
    max_web_bytes: int = Field(default=2 * 1024 * 1024, ge=1)
    web_timeout_seconds: float = Field(default=20.0, gt=0, le=60)
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str | None = None
    azure_openai_model: str | None = None
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
