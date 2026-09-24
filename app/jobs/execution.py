"""Execution checkpoints around the approved handlers; no in-process background jobs."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.job_models import (
    JobBudget,
    ResearchPlan,
    ResearchTask,
    TaskAttempt,
    TaskDependency,
)
from app.db.research_models import ResearchGap, ResearchResult, ResearchRun, ResearchRunSource
from app.embeddings.azure_openai import AzureEmbeddingConfigurationError, AzureEmbeddingError
from app.errors import NexusError
from app.jobs.contracts import TERMINAL_JOBS, canonical_hash, validate_plan
from app.jobs.handlers import HANDLERS
from app.jobs.planner import PLANNER_PROMPT_VERSION, propose_plan
from app.jobs.service import schedule_ready, stop_pending
from app.jobs.state import check_active, event, finish_job, locked_job
from app.llm.azure_openai import AzureLLMConfigurationError, AzureLLMError, AzureLLMOutputError

logger = logging.getLogger(__name__)


class RetryableTaskError(RuntimeError):
    """The worker package applies bounded backoff only to explicitly classified failures."""


def classify_failure(error: Exception, *, planning: bool = False) -> NexusError:
    if isinstance(error, NexusError):
        return error
    if isinstance(error, (AzureEmbeddingConfigurationError, AzureLLMConfigurationError)):
        return NexusError(
            "PROVIDER_NOT_CONFIGURED", "The configured Azure provider is incomplete.", 503
        )
    if isinstance(error, (AzureLLMOutputError, ValidationError)):
        return NexusError(
            "PLAN_INVALID" if planning else "STRUCTURED_RESULT_INVALID",
            "The provider refused or returned an invalid structured response.",
            502,
        )
    if isinstance(error, (AzureEmbeddingError, AzureLLMError)):
        status = getattr(error.__cause__, "status_code", None)
        return NexusError(
            "PROVIDER_FAILED",
            "The configured Azure request failed.",
            502,
            retryable=status is None or status in {408, 409, 429} or status >= 500,
        )
    if isinstance(error, SQLAlchemyError):
        return NexusError(
            "DATABASE_UNAVAILABLE", "The task could not persist its work.", 503, retryable=True
        )
    logger.error("task_internal_error type=%s", type(error).__name__)
    return NexusError("INTERNAL_ERROR", "An unexpected task error occurred.", 500)


def provider_settings(db, job, settings):
    run = db.get(ResearchRun, job.run_id)
    remaining = settings.job_timeout_seconds
    if job.started_at:
        budget = db.get(JobBudget, job.id)
        remaining = (
            budget.limits["max_duration_seconds"]
            - (datetime.now(timezone.utc) - job.started_at).total_seconds()
        )
    return settings.model_copy(
        update={
            "azure_openai_model": run.llm_deployment,
            "azure_openai_embedding_deployment": run.retrieval_config["embedding_deployment"],
            "azure_openai_embedding_dimensions": run.retrieval_config["embedding_dimensions"],
            "provider_timeout_seconds": max(0.1, min(settings.provider_timeout_seconds, remaining)),
            "web_timeout_seconds": max(0.1, min(settings.web_timeout_seconds, remaining)),
        }
    )


def plan_job(db, job_id: UUID, settings) -> None:
    job = locked_job(db, job_id)
    if job.status in TERMINAL_JOBS:
        return
    budget = db.get(JobBudget, job.id)
    try:
        check_active(job, budget)
        existing = db.scalar(select(ResearchPlan).where(ResearchPlan.job_id == job.id))
        if existing and existing.status == "validated":
            schedule_ready(db, job)
            db.commit()
            return
        if job.planning_attempts >= 3:
            raise NexusError(
                "TASK_RETRY_EXHAUSTED", "Planning was interrupted too many times.", 409
            )
        job.planning_attempts += 1
        job.status = "planning"
        job.started_at = job.started_at or datetime.now(timezone.utc)
        event(db, job, "planning_started", attempt=job.planning_attempts)
        db.commit()
        plan, model = propose_plan(db, job, budget, provider_settings(db, job, settings))
        job = locked_job(db, job_id)
        check_active(job, db.get(JobBudget, job.id, populate_existing=True))
        source_ids = set(
            str(value)
            for value in db.scalars(
                select(ResearchRunSource.source_id).where(
                    ResearchRunSource.research_run_id == job.run_id
                )
            )
        )
        stored = ResearchPlan(
            job_id=job.id,
            schema_version=plan.schema_version,
            status="generated",
            graph_hash=canonical_hash(plan.model_dump()),
            plan_json=plan.model_dump(),
            planner_provider=model,
            prompt_version=PLANNER_PROMPT_VERSION,
        )
        db.add(stored)
        event(db, job, "plan_created", schema_version=plan.schema_version)
        try:
            validate_plan(
                plan,
                source_ids=source_ids,
                web_urls=job.policy["web_urls"],
                limits=budget.limits,
                mode=job.mode,
            )
        except NexusError as error:
            stored.status, stored.rejection_code = "rejected", error.code
            event(db, job, "plan_rejected", error_code=error.code)
            finish_job(db, job, "failed", error)
            db.commit()
            return
        stored.status, stored.validated_at = "validated", datetime.now(timezone.utc)
        db.flush()
        tasks = {}
        for proposed in plan.tasks:
            task = ResearchTask(
                job_id=job.id,
                plan_id=stored.id,
                task_key=proposed.key,
                task_type=proposed.type,
                optional=proposed.optional,
                input_json=proposed.input.model_dump(),
                idempotency_key=canonical_hash(
                    {
                        "job_id": str(job.id),
                        "task": proposed.model_dump(),
                        "plan_version": plan.schema_version,
                        "prompt_version": PLANNER_PROMPT_VERSION,
                    }
                ),
            )
            db.add(task)
            tasks[proposed.key] = task
        db.flush()
        for proposed in plan.tasks:
            db.add_all(
                [
                    TaskDependency(
                        job_id=job.id,
                        task_id=tasks[proposed.key].id,
                        depends_on_task_id=tasks[parent].id,
                    )
                    for parent in proposed.depends_on
                ]
            )
        db.flush()
        job.status = "planned"
        event(db, job, "plan_validated", task_count=len(tasks), graph_hash=stored.graph_hash)
        schedule_ready(db, job)
        db.commit()
    except Exception as exc:
        db.rollback()
        error = classify_failure(exc, planning=True)
        job = locked_job(db, job_id)
        try:
            check_active(job, db.get(JobBudget, job.id))
        except NexusError as stopped:
            error = stopped
        if job.cancel_requested_at:
            finish_job(db, job, "cancelled")
        elif error.retryable and job.planning_attempts < 3:
            job.status = "created"
            event(db, job, "planning_retry_scheduled", error_code=error.code)
            db.commit()
            raise RetryableTaskError(error.code) from None
        else:
            finish_job(db, job, "failed", error)
        db.commit()


def execute_task(db, task_id: UUID, settings, *, worker_id: str = "local-worker") -> None:
    identity = db.get(ResearchTask, task_id)
    if identity is None:
        return
    job_id = identity.job_id
    job = locked_job(db, job_id)
    task = db.get(ResearchTask, task_id, populate_existing=True)
    if task.state == "succeeded":
        event(db, job, "task_delivery_reused", task=task, task_key=task.task_key)
        db.commit()
        return
    if job.status in TERMINAL_JOBS or task.state in {"cancelled", "skipped", "failed"}:
        return
    parents = db.scalars(
        select(ResearchTask)
        .join(TaskDependency, ResearchTask.id == TaskDependency.depends_on_task_id)
        .where(TaskDependency.task_id == task_id)
    ).all()
    if not all(
        parent.state == "succeeded" or (parent.optional and parent.state == "failed")
        for parent in parents
    ):
        event(db, job, "task_delivery_deferred", task=task, reason="dependencies_not_ready")
        db.commit()
        return
    attempt = None
    try:
        budget = db.get(JobBudget, job.id)
        check_active(job, budget)
        if task.attempt_count >= task.max_attempts:
            raise NexusError(
                "TASK_RETRY_EXHAUSTED", "The task exhausted its execution attempts.", 409
            )
        for interrupted in db.scalars(
            select(TaskAttempt).where(
                TaskAttempt.task_id == task.id, TaskAttempt.status == "started"
            )
        ):
            interrupted.status, interrupted.error_code = "interrupted", "WORKER_INTERRUPTED"
            interrupted.completed_at = datetime.now(timezone.utc)
            event(db, job, "task_recovered", task=task, previous_attempt=interrupted.attempt_number)
        if task.attempt_count == 0:
            budget.used_tasks += 1
        task.attempt_count += 1
        task.state, task.worker_id, task.error_code = "running", worker_id, None
        task.started_at = task.started_at or datetime.now(timezone.utc)
        attempt = TaskAttempt(
            task_id=task.id,
            attempt_number=task.attempt_count,
            worker_id=worker_id,
            status="started",
            provider_usage={},
        )
        db.add(attempt)
        event(
            db,
            job,
            "task_started",
            task=task,
            task_key=task.task_key,
            attempt=task.attempt_count,
            worker_id=worker_id,
        )
        db.commit()
        output = HANDLERS[task.task_type](
            db, job, task, attempt, provider_settings(db, job, settings)
        )
        job = locked_job(db, job_id)
        check_active(job, db.get(JobBudget, job.id, populate_existing=True))
        task.state, task.output_ref = "succeeded", output
        task.completed_at = datetime.now(timezone.utc)
        attempt.status, attempt.completed_at = "succeeded", task.completed_at
        event(db, job, "task_succeeded", task=task, task_key=task.task_key)
        db.flush()
        if task.task_type == "validate_result":
            result = db.get(ResearchResult, UUID(output["result_id"]))
            gaps = db.scalar(
                select(func.count())
                .select_from(ResearchGap)
                .where(ResearchGap.research_run_id == job.run_id)
            )
            finish_job(
                db,
                job,
                "completed_with_gaps"
                if gaps or result.status == "insufficient_context"
                else "completed",
            )
        else:
            schedule_ready(db, job)
        db.commit()
    except Exception as exc:
        db.rollback()
        error = classify_failure(exc)
        job = locked_job(db, job_id)
        try:
            check_active(job, db.get(JobBudget, job.id))
        except NexusError as stopped:
            error = stopped
        task = db.get(ResearchTask, task_id, populate_existing=True)
        attempt = db.scalar(
            select(TaskAttempt).where(
                TaskAttempt.task_id == task.id, TaskAttempt.attempt_number == task.attempt_count
            )
        )
        retry = (
            error.retryable
            and task.attempt_count < task.max_attempts
            and not job.cancel_requested_at
            and job.status not in TERMINAL_JOBS
        )
        if attempt:
            attempt.status = (
                "cancelled"
                if job.cancel_requested_at
                else ("retryable_failure" if retry else "permanent_failure")
            )
            attempt.error_code, attempt.completed_at = error.code, datetime.now(timezone.utc)
        task.error_code = error.code
        if job.cancel_requested_at or error.code == "JOB_CANCELLED":
            task.state, task.completed_at = "cancelled", datetime.now(timezone.utc)
            stop_pending(db, job, cancelled=True)
            db.flush()
            active = db.scalar(
                select(func.count())
                .select_from(ResearchTask)
                .where(ResearchTask.job_id == job.id, ResearchTask.state == "running")
            )
            if not active:
                finish_job(db, job, "cancelled")
        elif retry:
            task.state = "retry_wait"
            event(
                db,
                job,
                "task_retry_scheduled",
                task=task,
                error_code=error.code,
                attempt=task.attempt_count,
            )
        else:
            task.state, task.completed_at = "failed", datetime.now(timezone.utc)
            event(db, job, "task_failed", task=task, task_key=task.task_key, error_code=error.code)
            if (
                task.optional
                and error.code != "BUDGET_EXCEEDED"
                and job.status not in TERMINAL_JOBS
            ):
                db.flush()
                schedule_ready(db, job)
            else:
                stop_pending(db, job, cancelled=False)
                finish_job(db, job, "failed", error)
        db.commit()
        if retry:
            raise RetryableTaskError(error.code) from None
