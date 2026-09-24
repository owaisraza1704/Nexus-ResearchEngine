"""Local research workspaces and durable execution; queue delivery belongs to Procrastinate."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkspaceSource(Base):
    __tablename__ = "workspace_sources"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchJob(Base):
    __tablename__ = "research_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_job_request"),
        CheckConstraint(
            "status IN ('created','planning','planned','running','completed',"
            "'completed_with_gaps','failed','cancel_requested','cancelled')",
            name="ck_job_status",
        ),
        CheckConstraint(
            "mode IN ('answer','comparison','synthesis','evidence','agentic')",
            name="ck_job_mode",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"), unique=True)
    question: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(32))
    request_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    policy_version: Mapped[str] = mapped_column(String(64), default="local-approved-sources.v1")
    policy: Mapped[dict] = mapped_column(JSONB, default=dict)
    queue_job_id: Mapped[int | None] = mapped_column(BigInteger)
    planning_attempts: Mapped[int] = mapped_column(Integer, default=0)
    event_sequence: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobBudget(Base):
    __tablename__ = "job_budgets"

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_jobs.id", ondelete="CASCADE"), primary_key=True
    )
    limits: Mapped[dict] = mapped_column(JSONB)
    used_provider_calls: Mapped[int] = mapped_column(Integer, default=0)
    used_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    used_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reserved_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reserved_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    unknown_usage_calls: Mapped[int] = mapped_column(Integer, default=0)
    used_tasks: Mapped[int] = mapped_column(Integer, default=0)


class ResearchPlan(Base):
    __tablename__ = "research_plans"
    __table_args__ = (UniqueConstraint("job_id", "id", name="uq_plan_job_identity"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_jobs.id", ondelete="CASCADE"), unique=True
    )
    schema_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    graph_hash: Mapped[str] = mapped_column(String(64))
    plan_json: Mapped[dict] = mapped_column(JSONB)
    planner_provider: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(64))
    rejection_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResearchTask(Base):
    __tablename__ = "research_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "plan_id"],
            ["research_plans.job_id", "research_plans.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("job_id", "task_key", name="uq_job_task_key"),
        UniqueConstraint("job_id", "id", name="uq_task_job_identity"),
        CheckConstraint(
            "state IN ('pending','ready','running','retry_wait','succeeded',"
            "'failed','cancelled','skipped')",
            name="ck_task_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    task_key: Mapped[str] = mapped_column(String(80))
    task_type: Mapped[str] = mapped_column(String(40))
    optional: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str] = mapped_column(String(32), default="pending")
    input_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_ref: Mapped[dict | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    queue_job_id: Mapped[int | None] = mapped_column(BigInteger)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    worker_id: Mapped[str | None] = mapped_column(String(200))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "task_id"],
            ["research_tasks.job_id", "research_tasks.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_id", "depends_on_task_id"],
            ["research_tasks.job_id", "research_tasks.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("task_id <> depends_on_task_id", name="ck_dependency_not_self"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)


class TaskAttempt(Base):
    __tablename__ = "task_attempts"
    __table_args__ = (UniqueConstraint("task_id", "attempt_number", name="uq_task_attempt"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_tasks.id", ondelete="CASCADE"), index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    provider_usage: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (UniqueConstraint("job_id", "sequence", name="uq_job_event_sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_jobs.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("research_tasks.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExternalSource(Base):
    __tablename__ = "external_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_tasks.id"), unique=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    provider: Mapped[str] = mapped_column(String(64), default="approved_url")
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
    source_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResultReview(Base):
    __tablename__ = "result_reviews"
    __table_args__ = (
        CheckConstraint("groundedness BETWEEN 1 AND 5", name="ck_review_groundedness"),
        CheckConstraint("relevance BETWEEN 1 AND 5", name="ck_review_relevance"),
        CheckConstraint("citation_quality BETWEEN 1 AND 5", name="ck_review_citations"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_jobs.id", ondelete="CASCADE"), primary_key=True
    )
    groundedness: Mapped[int] = mapped_column(Integer)
    relevance: Mapped[int] = mapped_column(Integer)
    citation_quality: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
