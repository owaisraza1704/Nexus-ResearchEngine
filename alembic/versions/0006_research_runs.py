"""Pin bounded multi-document runs and record every selected source."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_research_runs"
down_revision = "0005_query_answers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("retrieval_config", postgresql.JSONB(), nullable=False),
        sa.Column("answer_config", postgresql.JSONB(), nullable=False),
        sa.Column("embedding_provider", sa.String(50), nullable=False),
        sa.Column("llm_provider", sa.String(50), nullable=False),
        sa.Column("llm_deployment", sa.String(200), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("embedding_tokens", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("retrieval_ms", sa.Integer(), nullable=False),
        sa.Column("synthesis_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("mode IN ('comparison', 'synthesis')", name="ck_research_run_mode"),
        sa.CheckConstraint(
            "status IN ('created', 'retrieving', 'synthesizing', 'completed', "
            "'insufficient_context', 'failed')",
            name="ck_research_run_status",
        ),
    )
    op.create_index("ix_research_runs_created_at", "research_runs", ["created_at"])
    op.create_table(
        "research_run_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("research_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("source_order", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.UniqueConstraint("research_run_id", "source_id", name="uq_run_source"),
        sa.UniqueConstraint("research_run_id", "document_id", name="uq_run_document"),
        sa.UniqueConstraint("research_run_id", "source_order", name="uq_run_source_order"),
        sa.UniqueConstraint("research_run_id", "id", name="uq_run_source_identity"),
    )
    op.create_table(
        "source_coverage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("research_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_run_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("retrieved_chunk_count", sa.Integer(), nullable=False),
        sa.Column("selected_chunk_count", sa.Integer(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("context_limited", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["research_run_id", "research_run_source_id"],
            ["research_run_sources.research_run_id", "research_run_sources.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("research_run_id", "research_run_source_id", name="uq_source_coverage"),
        sa.CheckConstraint(
            "status IN ('pending', 'retrieved', 'used', 'no_relevant_evidence', "
            "'parse_unavailable', 'retrieval_failed', 'context_limited', 'not_processed')",
            name="ck_source_coverage_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("source_coverage")
    op.drop_table("research_run_sources")
    op.drop_table("research_runs")
