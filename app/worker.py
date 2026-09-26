"""Run with: uv run celery -A app.worker:celery_app worker --loglevel=INFO."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.job_models import QueueDelivery
from app.db.models import Source
from app.db.session import SessionLocal, engine
from app.ingestion.service import ingest_source
from app.jobs.celery_app import celery_app
from app.jobs.execution import RetryableTaskError, classify_failure, execute_task, plan_job
from app.jobs.queue import publish_pending

# HTTP INFO logs include approved URLs, which may contain private query strings.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
settings = get_settings()


def ingest_upload(db: Session, source_id: str) -> None:
    source = db.get(Source, UUID(source_id))
    if source is None or source.status == "ready":
        return
    if source.ingestion_attempts >= 3:
        source.status, source.error_code = "failed", "TASK_RETRY_EXHAUSTED"
        source.error_detail = "The upload was interrupted too many times. Retry it explicitly."
        db.commit()
        return
    source.ingestion_attempts += 1
    source.status = "processing"
    db.commit()
    name = source.artifact_name or (
        source.content_sha256 + Path(source.original_filename).suffix.lower()
    )
    path = settings.artifact_store_path / Path(name).name
    try:
        ingest_source(db, source, path, settings)
    except Exception as failure:
        db.rollback()
        error = classify_failure(failure)
        source = db.get(Source, UUID(source_id))
        source.status, source.error_code, source.error_detail = "failed", error.code, str(error)
        if error.retryable and source.ingestion_attempts < 3:
            source.status = "processing"
            db.commit()
            raise RetryableTaskError(error.code) from None
        db.commit()


@celery_app.task(
    name="nexus.deliver",
    bind=True,
    autoretry_for=(RetryableTaskError, SQLAlchemyError),
    retry_backoff=2,
    retry_jitter=False,
    max_retries=3,
)
def deliver(self, delivery_id: int) -> None:
    # One physical connection keeps the session lock across handler commits.
    # A crash releases it; duplicate Celery deliveries cannot execute simultaneously.
    with engine.connect() as connection:
        with Session(bind=connection, autoflush=False) as db:
            delivery = db.get(QueueDelivery, delivery_id)
            if delivery is None or delivery.finished_at or delivery.cancelled_at:
                return
            key = delivery.lock_key
            acquired = db.scalar(
                text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"),
                {"key": key},
            )
            db.commit()
            if not acquired:
                return
            try:
                db.refresh(delivery)
                if delivery.finished_at or delivery.cancelled_at:
                    return
                if delivery.task_name == "nexus.plan":
                    plan_job(db, UUID(delivery.args["job_id"]), settings)
                elif delivery.task_name == "nexus.execute":
                    execute_task(
                        db,
                        UUID(delivery.args["task_id"]),
                        settings,
                        worker_id=self.request.hostname or "local-celery-worker",
                    )
                elif delivery.task_name == "nexus.ingest":
                    ingest_upload(db, delivery.args["source_id"])
                else:
                    raise ValueError("Unknown delivery task")
                delivery.finished_at = datetime.now(timezone.utc)
                db.commit()
            finally:
                db.rollback()
                db.execute(
                    text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"),
                    {"key": key},
                )
                db.commit()
    # Beat covers a crash before newly unblocked dependencies are published here.
    dispatch()


@celery_app.task(name="nexus.dispatch")
def dispatch() -> int:
    with SessionLocal() as db:
        return publish_pending(db)
