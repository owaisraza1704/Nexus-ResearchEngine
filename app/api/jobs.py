import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.projects import project_or_404
from app.api.research import _result_response
from app.config import Settings, get_settings
from app.db.job_models import (
    ExternalSource,
    JobEvent,
    ResearchJob,
    ResearchPlan,
    ResearchTask,
    ResultReview,
    TaskAttempt,
    TaskDependency,
)
from app.db.research_models import ResearchResult
from app.db.session import get_db
from app.errors import NexusError
from app.jobs.contracts import JobRequest
from app.jobs.service import cancel_job, create_job, job_progress

router = APIRouter(prefix="/v1/research/jobs", tags=["asynchronous research"])


def get_job(db: Session, job_id: UUID) -> ResearchJob:
    job = db.get(ResearchJob, job_id)
    if job is None:
        raise NexusError("JOB_NOT_FOUND", "This research job does not exist.", 404)
    return job


@router.post("", status_code=202)
def submit_job(
    request: JobRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return job_progress(db, create_job(db, request, settings))


@router.get("")
def list_jobs(
    workspace_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    project_or_404(db, workspace_id)
    query = select(ResearchJob).where(ResearchJob.workspace_id == workspace_id)
    jobs = db.scalars(query.order_by(ResearchJob.created_at.desc()).limit(limit).offset(offset))
    return {
        "jobs": [job_progress(db, job) for job in jobs],
        "limit": limit,
        "offset": offset,
        "total": db.scalar(
            select(func.count())
            .select_from(ResearchJob)
            .where(ResearchJob.workspace_id == workspace_id)
        ),
    }


@router.get("/{job_id}")
def job_status(job_id: UUID, db: Session = Depends(get_db)):
    return job_progress(db, get_job(db, job_id))


@router.get("/{job_id}/plan")
def job_plan(job_id: UUID, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    plan = db.scalar(select(ResearchPlan).where(ResearchPlan.job_id == job.id))
    if plan is None:
        return {"job_id": job.id, "status": "pending", "tasks": []}
    return {
        "job_id": job.id,
        "plan_id": plan.id,
        "status": plan.status,
        "schema_version": plan.schema_version,
        "graph_hash": plan.graph_hash,
        "planner_provider": plan.planner_provider,
        "prompt_version": plan.prompt_version,
        "rejection_code": plan.rejection_code,
        "tasks": plan.plan_json["tasks"],
    }


@router.get("/{job_id}/tasks")
def job_tasks(job_id: UUID, db: Session = Depends(get_db)):
    get_job(db, job_id)
    tasks = db.scalars(
        select(ResearchTask)
        .where(ResearchTask.job_id == job_id)
        .order_by(ResearchTask.created_at, ResearchTask.task_key)
    ).all()
    by_id = {task.id: task.task_key for task in tasks}
    edges = db.execute(
        select(TaskDependency.task_id, TaskDependency.depends_on_task_id).where(
            TaskDependency.job_id == job_id
        )
    ).all()
    attempts = (
        db.scalars(
            select(TaskAttempt)
            .where(TaskAttempt.task_id.in_(by_id))
            .order_by(TaskAttempt.attempt_number)
        ).all()
        if tasks
        else []
    )
    return {
        "job_id": job_id,
        "tasks": [
            {
                "task_id": task.id,
                "key": task.task_key,
                "type": task.task_type,
                "state": task.state,
                "optional": task.optional,
                "input": task.input_json,
                "depends_on": [by_id[parent] for child, parent in edges if child == task.id],
                "output_ref": {
                    key: value
                    for key, value in (task.output_ref or {}).items()
                    if key not in {"generated", "candidates"}
                },
                "candidate_count": len((task.output_ref or {}).get("candidates", [])),
                "attempt_count": task.attempt_count,
                "max_attempts": task.max_attempts,
                "worker_id": task.worker_id,
                "error_code": task.error_code,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "attempts": [
                    {
                        "attempt_number": attempt.attempt_number,
                        "status": attempt.status,
                        "error_code": attempt.error_code,
                        "worker_id": attempt.worker_id,
                        "started_at": attempt.started_at,
                        "completed_at": attempt.completed_at,
                        "usage": attempt.provider_usage,
                    }
                    for attempt in attempts
                    if attempt.task_id == task.id
                ],
            }
            for task in tasks
        ],
    }


@router.get("/{job_id}/events")
def job_events(
    job_id: UUID,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    get_job(db, job_id)
    rows = db.scalars(
        select(JobEvent)
        .where(JobEvent.job_id == job_id, JobEvent.sequence > after)
        .order_by(JobEvent.sequence)
        .limit(limit + 1)
    ).all()
    return {
        "job_id": job_id,
        "events": [
            {
                "sequence": row.sequence,
                "event_type": row.event_type,
                "task_id": row.task_id,
                "payload": row.payload,
                "created_at": row.created_at,
            }
            for row in rows[:limit]
        ],
        "next_cursor": rows[min(limit, len(rows)) - 1].sequence if rows else after,
        "has_more": len(rows) > limit,
    }


@router.post("/{job_id}/cancel", status_code=202)
def request_cancellation(job_id: UUID, db: Session = Depends(get_db)):
    job = cancel_job(db, job_id)
    return {"job_id": job.id, "status": job.status}


@router.get("/{job_id}/result")
def job_result(job_id: UUID, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job.status not in {"completed", "completed_with_gaps"}:
        raise NexusError(
            "RESULT_NOT_READY", "This job has no completed, validated result.", 409, job_id=job.id
        )
    result = db.scalar(select(ResearchResult).where(ResearchResult.research_run_id == job.run_id))
    if result is None:
        raise NexusError(
            "RESULT_VALIDATION_FAILED", "The saved result is unavailable.", 409, job_id=job.id
        )
    body = _result_response(db, result).model_dump(mode="json")
    failures = db.scalars(
        select(ResearchTask).where(ResearchTask.job_id == job.id, ResearchTask.state == "failed")
    ).all()
    external = db.scalars(
        select(ExternalSource).join(ResearchTask).where(ResearchTask.job_id == job.id)
    ).all()
    review = db.get(ResultReview, job.id)
    return {
        **body,
        "job_id": str(job.id),
        "workspace_id": str(job.workspace_id),
        "status": job.status,
        "outcome": result.status,
        "mode": job.mode,
        "budget": job_progress(db, job)["budget"],
        "task_failures": [
            {"task_key": task.task_key, "error_code": task.error_code} for task in failures
        ],
        "external_sources": [
            {
                "source_id": str(source.source_id),
                "document_id": str(source.document_id),
                "url": source.url,
                "canonical_url": source.canonical_url,
                "title": source.title,
                "retrieved_at": source.retrieved_at.isoformat(),
                "content_sha256": source.content_sha256,
            }
            for source in external
        ],
        "review": {
            "groundedness": review.groundedness,
            "relevance": review.relevance,
            "citation_quality": review.citation_quality,
            "notes": review.notes,
            "reviewed_at": review.reviewed_at.isoformat(),
        }
        if review
        else None,
    }


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    groundedness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    citation_quality: int = Field(ge=1, le=5)
    notes: str = Field(default="", max_length=4000)


@router.put("/{job_id}/review")
def review_result(job_id: UUID, request: ReviewRequest, db: Session = Depends(get_db)):
    job_result(job_id, db)
    values = {**request.model_dump(), "reviewed_at": datetime.now(timezone.utc)}
    db.execute(
        insert(ResultReview)
        .values(job_id=job_id, **values)
        .on_conflict_do_update(
            index_elements=["job_id"],
            set_=values,
        )
    )
    db.commit()
    return {"job_id": job_id, **values}


@router.get("/{job_id}/export")
def export_result(job_id: UUID, format: str = "markdown", db: Session = Depends(get_db)):
    body = job_result(job_id, db)
    if format == "json":
        content, mime, extension = (
            json.dumps(body, indent=2, ensure_ascii=False),
            "application/json",
            "json",
        )
    elif format == "markdown":
        parts = [
            f"# {body['question']}",
            "",
            f"Status: {body['status']}",
            "",
            body["summary"],
            "",
            "## Claims",
            "",
        ]
        parts.extend(
            f"- {claim['text']} {' '.join('[' + label + ']' for label in claim['evidence'])}"
            for claim in body["claims"]
        )
        parts.extend(["", "## Evidence", ""])
        for item in body["evidence"]:
            parts.extend(
                [
                    f"### [{item['label']}] {item['display_text']}",
                    "",
                    item["excerpt"],
                    "",
                    "Locator: " + json.dumps(item["locator"], ensure_ascii=False),
                    "",
                ]
            )
        parts.extend(["## Gaps and limitations", ""])
        parts.extend(f"- {gap['text']}" for gap in body["gaps"])
        if body["mode"] == "evidence":
            parts.append("These are retrieval candidates, not verified answers.")
        content, mime, extension = "\n".join(parts), "text/markdown", "md"
    else:
        raise NexusError("INVALID_REQUEST", "Export format must be markdown or json.")
    return Response(
        content,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="nexus-report-{job_id}.{extension}"',
        },
    )
