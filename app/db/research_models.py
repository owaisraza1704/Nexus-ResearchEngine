"""Persistence for bounded multi-document runs, separate from MVP-1 answers."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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


class ResearchRun(Base):
    __tablename__ = "research_runs"
    __table_args__ = (
        CheckConstraint("mode IN ('comparison', 'synthesis')", name="ck_research_run_mode"),
        CheckConstraint(
            "status IN ('created', 'retrieving', 'synthesizing', 'completed', "
            "'insufficient_context', 'failed')",
            name="ck_research_run_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    retrieval_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    answer_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_deployment: Mapped[str | None] = mapped_column(String(200), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrieval_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synthesis_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchRunSource(Base):
    __tablename__ = "research_run_sources"
    __table_args__ = (
        UniqueConstraint("research_run_id", "source_id", name="uq_run_source"),
        UniqueConstraint("research_run_id", "document_id", name="uq_run_document"),
        UniqueConstraint("research_run_id", "source_order", name="uq_run_source_order"),
        UniqueConstraint("research_run_id", "id", name="uq_run_source_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    document_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_order: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SourceCoverage(Base):
    __tablename__ = "source_coverage"
    __table_args__ = (
        ForeignKeyConstraint(
            ["research_run_id", "research_run_source_id"],
            ["research_run_sources.research_run_id", "research_run_sources.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("research_run_id", "research_run_source_id", name="uq_source_coverage"),
        CheckConstraint(
            "status IN ('pending', 'retrieved', 'used', 'no_relevant_evidence', "
            "'parse_unavailable', 'retrieval_failed', 'context_limited', 'not_processed')",
            name="ck_source_coverage_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    research_run_source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    retrieved_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResearchRetrievalResult(Base):
    __tablename__ = "research_retrieval_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["research_run_id", "research_run_source_id"],
            ["research_run_sources.research_run_id", "research_run_sources.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("research_run_id", "chunk_id", name="uq_research_retrieval_chunk"),
        UniqueConstraint("research_run_source_id", "source_rank", name="uq_research_source_rank"),
        UniqueConstraint(
            "research_run_id", "id", "chunk_id", name="uq_research_retrieval_identity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    research_run_source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_chunks.id"), nullable=False)
    source_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    ranking: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["research_run_id", "retrieval_result_id", "chunk_id"],
            [
                "research_retrieval_results.research_run_id",
                "research_retrieval_results.id",
                "research_retrieval_results.chunk_id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint("research_run_id", "chunk_id", name="uq_research_evidence_chunk"),
        UniqueConstraint("research_run_id", "label", name="uq_research_evidence_label"),
        UniqueConstraint("research_run_id", "id", name="uq_research_evidence_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    retrieval_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    locator_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("research_run_id", "sequence", name="uq_research_claim_sequence"),
        UniqueConstraint("research_run_id", "id", name="uq_research_claim_identity"),
        CheckConstraint(
            "support_status IN ('supported', 'partially_supported', 'contradicted', 'unresolved')",
            name="ck_claim_support_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    support_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["research_run_id", "claim_id"],
            ["claims.research_run_id", "claims.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["research_run_id", "evidence_item_id"],
            ["evidence_items.research_run_id", "evidence_items.id"],
        ),
        UniqueConstraint("claim_id", "evidence_item_id", "relationship", name="uq_claim_evidence"),
        CheckConstraint(
            "relationship IN ('supports', 'contradicts', 'qualifies', 'context')",
            name="ck_claim_evidence_relationship",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    relationship: Mapped[str] = mapped_column(String(32), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResearchGap(Base):
    __tablename__ = "research_gaps"
    __table_args__ = (
        UniqueConstraint("research_run_id", "sequence", name="uq_research_gap_sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    gap_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchResult(Base):
    __tablename__ = "research_results"
    __table_args__ = (
        UniqueConstraint("research_run_id", "id", name="uq_research_result_identity"),
        CheckConstraint(
            "status IN ('completed', 'insufficient_context')", name="ck_research_result_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    limitation: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResultCitation(Base):
    __tablename__ = "result_citations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["research_run_id", "research_result_id"],
            ["research_results.research_run_id", "research_results.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["research_run_id", "evidence_item_id"],
            ["evidence_items.research_run_id", "evidence_items.id"],
        ),
        UniqueConstraint("research_result_id", "label", name="uq_research_citation_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    research_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    locator_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
