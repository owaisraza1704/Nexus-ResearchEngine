"""Small, explicit lifecycle rules; the database is authoritative, not browser state."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.job_models import JobBudget, JobEvent, ResearchJob, ResearchTask
from app.db.research_models import ResearchRun
from app.errors import NexusError
from app.jobs.contracts import TERMINAL_JOBS


def locked_job(db: Session, job_id: UUID) -> ResearchJob:
    job = db.scalar(
        select(ResearchJob)
        .where(ResearchJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if job is None:
        raise NexusError("JOB_NOT_FOUND", "The research job does not exist.", 404)
    return job


def event(
    db: Session, job: ResearchJob, kind: str, *, task: ResearchTask | None = None, **payload
) -> None:
    """Call while holding the job row lock so concurrent branches have one event order."""
    job.event_sequence += 1
    db.add(
        JobEvent(
            job_id=job.id,
            task_id=task.id if task else None,
            sequence=job.event_sequence,
            event_type=kind,
            payload=payload,
        )
    )


def check_active(job: ResearchJob, budget: JobBudget) -> None:
    if job.cancel_requested_at or job.status == "cancelled":
        raise NexusError("JOB_CANCELLED", "Cancellation was requested.", 409, job_id=job.id)
    if job.status in TERMINAL_JOBS:
        raise NexusError("JOB_TERMINAL", "This job has already finished.", 409, job_id=job.id)
    if job.started_at:
        elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
        if elapsed >= budget.limits["max_duration_seconds"]:
            raise NexusError("BUDGET_EXCEEDED", "The job execution deadline was exceeded.", 409)


def finish_job(db: Session, job: ResearchJob, status: str, error: NexusError | None = None) -> None:
    if job.status in TERMINAL_JOBS:
        return
    job.status = status
    job.completed_at = datetime.now(timezone.utc)
    if error:
        job.error_code = error.code
        job.error_detail = str(error)
    if status in {"failed", "cancelled"}:
        run = db.get(ResearchRun, job.run_id)
        run.status = "failed"
        run.error_code = job.error_code or "JOB_CANCELLED"
        run.error_detail = job.error_detail or "The research job was cancelled."
        run.completed_at = job.completed_at
    event(
        db,
        job,
        f"job_{'completed' if status == 'completed_with_gaps' else status}",
        status=status,
        error_code=job.error_code,
    )
