"""Accept and inspect local research work without holding an HTTP request open."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.job_models import (
    JobBudget,
    JobEvent,
    ResearchJob,
    ResearchTask,
    TaskDependency,
    WorkspaceSource,
)
from app.db.models import Workspace
from app.errors import NexusError
from app.jobs.contracts import (
    TERMINAL_JOBS,
    TERMINAL_TASKS,
    JobRequest,
    budget_limits,
    canonical_hash,
)
from app.jobs.queue import enqueue, producer
from app.jobs.state import check_active, event, finish_job, locked_job
from app.jobs.web import validate_web_policy
from app.research.service import create_run


def create_job(db: Session, request: JobRequest, settings: Settings) -> ResearchJob:
    workspace = db.scalar(
        select(Workspace).where(Workspace.id == request.workspace_id).with_for_update()
    )
    if workspace is None:
        raise NexusError("WORKSPACE_NOT_FOUND", "This research workspace does not exist.", 404)
    fingerprint = canonical_hash(request.model_dump(mode="json", exclude={"idempotency_key"}))
    if request.idempotency_key:
        previous = db.scalar(
            select(ResearchJob).where(
                ResearchJob.workspace_id == workspace.id,
                ResearchJob.idempotency_key == request.idempotency_key,
            )
        )
        if previous is not None:
            if previous.request_hash != fingerprint:
                raise NexusError(
                    "IDEMPOTENCY_CONFLICT", "This request key was used with different inputs.", 409
                )
            return previous
    allowed = set(
        db.scalars(
            select(WorkspaceSource.source_id).where(WorkspaceSource.workspace_id == workspace.id)
        )
    )
    if not set(request.source_ids).issubset(allowed):
        raise NexusError("SOURCE_ACCESS_DENIED", "Select sources attached to this research.", 403)
    validate_web_policy(request.policy, settings)
    source_count = len(request.source_ids) + len(request.policy.web_urls)
    if not source_count or source_count > settings.max_research_sources:
        raise NexusError(
            "INVALID_SOURCE_SELECTION",
            f"Select 1–{settings.max_research_sources} internal or approved web sources.",
        )
    if request.mode == "answer" and source_count != 1:
        raise NexusError("INVALID_SOURCE_SELECTION", "Grounded Answer uses exactly one source.")
    if request.mode in {"comparison", "synthesis"} and source_count < 2:
        raise NexusError(
            "SOURCE_SET_TOO_SMALL", "Multi-document research needs at least two sources."
        )
    limits = budget_limits(request.budget, settings)
    run = create_run(
        db,
        request.question,
        request.source_ids,
        settings,
        mode="comparison" if request.mode == "comparison" else "synthesis",
        top_k_per_source=request.top_k_per_source,
        minimum_sources=0,
        commit=False,
    )
    run.answer_config = {
        **run.answer_config,
        "timeout_seconds": limits["max_duration_seconds"],
        "min_cited_sources": min(2, source_count),
    }
    job = ResearchJob(
        workspace_id=workspace.id,
        run_id=run.id,
        question=request.question,
        mode=request.mode,
        request_hash=fingerprint,
        idempotency_key=request.idempotency_key,
        status="created",
        policy=request.policy.model_dump(),
        event_sequence=0,
    )
    db.add(job)
    db.flush()
    db.add(JobBudget(job_id=job.id, limits=limits))
    event(db, job, "job_created", mode=job.mode, source_count=source_count)
    job.queue_job_id = enqueue(db, "nexus.plan", lock=f"plan:{job.id}", job_id=str(job.id))
    workspace.updated_at = datetime.now(timezone.utc)
    db.commit()
    return job


def schedule_ready(db: Session, job: ResearchJob) -> None:
    """Only lifecycle coordination is custom; the library delivers and leases queued work."""
    budget = db.get(JobBudget, job.id)
    check_active(job, budget)
    tasks = db.scalars(
        select(ResearchTask)
        .where(ResearchTask.job_id == job.id)
        .order_by(ResearchTask.created_at, ResearchTask.task_key)
    ).all()
    by_id = {task.id: task for task in tasks}
    edges = db.execute(
        select(TaskDependency.task_id, TaskDependency.depends_on_task_id).where(
            TaskDependency.job_id == job.id
        )
    ).all()
    active = sum(task.state in {"ready", "running", "retry_wait"} for task in tasks)
    for task in tasks:
        if task.state != "pending" or active >= budget.limits["max_parallel_tasks"]:
            continue
        parents = [by_id[parent] for child, parent in edges if child == task.id]
        # An optional web failure is an explicit gap, never evidence or a full success.
        if not all(
            parent.state == "succeeded" or (parent.optional and parent.state == "failed")
            for parent in parents
        ):
            continue
        task.state = "ready"
        task.queue_job_id = enqueue(
            db, "nexus.execute", lock=f"task:{task.id}", task_id=str(task.id)
        )
        event(db, job, "task_ready", task=task, task_key=task.task_key)
        active += 1
    if tasks and job.status == "planned":
        job.status = "running"


def stop_pending(db: Session, job: ResearchJob, *, cancelled: bool) -> None:
    for task in db.scalars(select(ResearchTask).where(ResearchTask.job_id == job.id)):
        if task.state in TERMINAL_TASKS or task.state == "running":
            continue
        if task.queue_job_id:
            producer.job_manager.cancel_job_by_id(
                task.queue_job_id, connection=db.connection().connection.driver_connection
            )
        task.state = "cancelled" if cancelled else "skipped"
        task.completed_at = datetime.now(timezone.utc)


def cancel_job(db: Session, job_id: UUID) -> ResearchJob:
    job = locked_job(db, job_id)
    if job.status in TERMINAL_JOBS:
        return job
    if not job.cancel_requested_at:
        job.cancel_requested_at = datetime.now(timezone.utc)
        event(db, job, "cancellation_requested")
    planning = job.status == "planning"
    job.status = "cancel_requested"
    stop_pending(db, job, cancelled=True)
    active = db.scalar(
        select(func.count())
        .select_from(ResearchTask)
        .where(ResearchTask.job_id == job.id, ResearchTask.state == "running")
    )
    if not planning and not active:
        if job.queue_job_id:
            producer.job_manager.cancel_job_by_id(
                job.queue_job_id, connection=db.connection().connection.driver_connection
            )
        finish_job(db, job, "cancelled")
    db.commit()
    return job


def job_progress(db: Session, job: ResearchJob) -> dict:
    counts = dict(
        db.execute(
            select(ResearchTask.state, func.count())
            .where(ResearchTask.job_id == job.id)
            .group_by(ResearchTask.state)
        ).all()
    )
    budget = db.get(JobBudget, job.id)
    finished_calls = db.scalar(
        select(func.count())
        .select_from(JobEvent)
        .where(JobEvent.job_id == job.id, JobEvent.event_type == "provider_call_finished")
    )
    return {
        "job_id": job.id,
        "workspace_id": job.workspace_id,
        "run_id": job.run_id,
        "question": job.question,
        "mode": job.mode,
        "status": job.status,
        "progress": {
            "total_tasks": sum(counts.values()),
            **{
                f"{state}_tasks": counts.get(state, 0)
                for state in (
                    "pending",
                    "ready",
                    "running",
                    "retry_wait",
                    "succeeded",
                    "failed",
                    "cancelled",
                    "skipped",
                )
            },
        },
        "budget": {
            **budget.limits,
            "used_tasks": budget.used_tasks,
            "used_provider_calls": budget.used_provider_calls,
            "used_input_tokens": budget.used_input_tokens,
            "used_output_tokens": budget.used_output_tokens,
            "reserved_input_tokens": budget.reserved_input_tokens,
            "reserved_output_tokens": budget.reserved_output_tokens,
            "unknown_usage_calls": (
                budget.unknown_usage_calls + budget.used_provider_calls - finished_calls
            ),
        },
        "policy": job.policy,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error": {"code": job.error_code, "message": job.error_detail} if job.error_code else None,
        "links": {
            kind: f"/v1/research/jobs/{job.id}{suffix}"
            for kind, suffix in (
                ("self", ""),
                ("plan", "/plan"),
                ("tasks", "/tasks"),
                ("events", "/events"),
                ("result", "/result"),
            )
        },
    }
