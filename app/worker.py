"""Run with: uv run procrastinate --app app.worker.worker worker"""

import logging
from pathlib import Path
from uuid import UUID

import procrastinate
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.db.models import Source
from app.db.session import SessionLocal
from app.ingestion.service import ingest_source
from app.jobs.execution import RetryableTaskError, classify_failure, execute_task, plan_job

# HTTP client INFO logs include full approved URLs, which may contain private query strings.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

settings = get_settings()
worker = procrastinate.App(
    connector=procrastinate.PsycopgConnector(
        conninfo=make_url(settings.database_url)
        .set(drivername="postgresql")
        .render_as_string(hide_password=False),
        min_size=1,
        max_size=5,
    ),
    worker_defaults={"concurrency": settings.worker_concurrency, "shutdown_graceful_timeout": 15},
)
retry = procrastinate.RetryStrategy(
    max_attempts=3,
    wait=2,
    exponential_wait=2,
    retry_exceptions={RetryableTaskError},
)


@worker.task(name="nexus.plan", queue="nexus", retry=retry)
def plan_research(job_id: str) -> None:
    with SessionLocal() as db:
        plan_job(db, UUID(job_id), settings)


@worker.task(name="nexus.execute", queue="nexus", retry=retry, pass_context=True)
def execute_research(context, task_id: str) -> None:
    with SessionLocal() as db:
        execute_task(db, UUID(task_id), settings, worker_id=context.worker_name or "local-worker")


@worker.task(name="nexus.ingest", queue="nexus", retry=retry)
def ingest_upload(source_id: str) -> None:
    with SessionLocal() as db:
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


@worker.periodic(cron="* * * * *")
@worker.task(name="nexus.recover", queue="maintenance", queueing_lock="nexus.recovery")
async def recover_stalled(timestamp: int) -> None:
    # Use the library's heartbeats, not elapsed task duration: a slow live worker
    # must never be mistaken for a dead worker.
    for job in await worker.job_manager.get_stalled_jobs(seconds_since_heartbeat=30):
        if job.task_name.startswith("nexus."):
            await worker.job_manager.retry_job(job)
