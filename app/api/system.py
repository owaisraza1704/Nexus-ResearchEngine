"""Safe local configuration and measured evaluation data; never expose credentials."""

from uuid import UUID

from fastapi import APIRouter, Depends
from kombu.exceptions import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.projects import project_or_404
from app.config import Settings, get_settings
from app.db.job_models import JobBudget, JobEvent, ResearchJob, ResearchPlan, ResultReview
from app.db.research_models import ResearchResult
from app.db.session import get_db
from app.jobs.celery_app import celery_app
from app.jobs.contracts import BudgetOptions, budget_limits

router = APIRouter(prefix="/v1", tags=["local operations and evaluation"])


@router.get("/system")
def local_system(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    try:
        workers = len(celery_app.control.inspect(timeout=0.5).ping() or {})
    except (OperationalError, RedisConnectionError, RedisTimeoutError, OSError):
        workers = 0
    return {
        "deployment": "local",
        "worker_count": workers,
        "queue_backend": "celery",
        "default_retrieval": "hybrid",
        "model": settings.azure_openai_model,
        "embedding_deployment": settings.azure_openai_embedding_deployment,
        "embedding_dimensions": settings.azure_openai_embedding_dimensions,
        "azure_configured": all(
            (
                settings.azure_openai_endpoint,
                settings.azure_openai_api_key,
                settings.azure_openai_api_version,
                settings.azure_openai_model,
                settings.azure_openai_embedding_deployment,
            )
        ),
        "supported_formats": ["PDF", "DOC", "DOCX"],
        "max_upload_bytes": settings.max_upload_bytes,
        "max_sources": settings.max_research_sources,
        "max_top_k": settings.max_top_k,
        "max_web_sources": settings.max_web_sources,
        "limits": budget_limits(BudgetOptions(), settings),
        "privacy": "Uploading authorizes the configured Azure services to process document text. "
        "Web acquisition requires explicitly approved public HTTPS URLs.",
    }


@router.get("/projects/{project_id}/evaluation")
def evaluate_project(project_id: UUID, db: Session = Depends(get_db)):
    project_or_404(db, project_id)
    rows = db.execute(
        select(ResearchJob, ResearchResult, JobBudget, ResultReview)
        .outerjoin(ResearchResult, ResearchResult.research_run_id == ResearchJob.run_id)
        .join(JobBudget, JobBudget.job_id == ResearchJob.id)
        .outerjoin(ResultReview, ResultReview.job_id == ResearchJob.id)
        .where(ResearchJob.workspace_id == project_id)
        .order_by(ResearchJob.created_at.desc())
    ).all()
    reviews = [review for _, _, _, review in rows if review]
    statuses = {}
    for job, _, _, _ in rows:
        statuses[job.status] = statuses.get(job.status, 0) + 1
    rejected = db.scalar(
        select(func.count())
        .select_from(ResearchPlan)
        .join(ResearchJob)
        .where(ResearchJob.workspace_id == project_id, ResearchPlan.status == "rejected")
    )
    finished_calls = db.scalar(
        select(func.count())
        .select_from(JobEvent)
        .join(ResearchJob)
        .where(
            ResearchJob.workspace_id == project_id,
            JobEvent.event_type == "provider_call_finished",
        )
    )
    return {
        "job_count": len(rows),
        "statuses": statuses,
        "rejected_plans": rejected,
        "provider_calls": sum(budget.used_provider_calls for _, _, budget, _ in rows),
        "input_tokens": sum(budget.used_input_tokens for _, _, budget, _ in rows),
        "output_tokens": sum(budget.used_output_tokens for _, _, budget, _ in rows),
        "unknown_usage_calls": sum(
            budget.unknown_usage_calls + budget.used_provider_calls for _, _, budget, _ in rows
        )
        - finished_calls,
        "review_count": len(reviews),
        "human_scores": {
            field: round(sum(getattr(review, field) for review in reviews) / len(reviews), 2)
            if reviews
            else None
            for field in ("groundedness", "relevance", "citation_quality")
        },
        "runs": [
            {
                "job_id": str(job.id),
                "question": job.question,
                "status": job.status,
                "outcome": result.status if result else None,
                "mode": job.mode,
                "duration_ms": result.duration_ms if result else None,
                "provider_calls": budget.used_provider_calls,
                "reviewed": review is not None,
            }
            for job, result, budget, review in rows
        ],
        "note": "These are measured execution statistics and your manual reviews. "
        "Recall, MRR, and semantic correctness require independently labeled evaluation cases.",
    }
