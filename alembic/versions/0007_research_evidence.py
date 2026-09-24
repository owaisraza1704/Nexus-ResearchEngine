"""Store per-source retrieval and immutable evidence context."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_research_evidence"
down_revision = "0006_research_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_retrieval_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("research_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_run_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["research_run_id", "research_run_source_id"],
            ["research_run_sources.research_run_id", "research_run_sources.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"]),
        sa.UniqueConstraint("research_run_id", "chunk_id", name="uq_research_retrieval_chunk"),
        sa.UniqueConstraint(
            "research_run_source_id", "source_rank", name="uq_research_source_rank"
        ),
        sa.UniqueConstraint(
            "research_run_id", "id", "chunk_id", name="uq_research_retrieval_identity"
        ),
    )
    op.create_table(
        "evidence_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("research_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retrieval_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(16), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("locator_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("source_display_name", sa.String(200), nullable=False),
        sa.Column("display_text", sa.Text(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["research_run_id", "retrieval_result_id", "chunk_id"],
            [
                "research_retrieval_results.research_run_id",
                "research_retrieval_results.id",
                "research_retrieval_results.chunk_id",
            ],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("research_run_id", "chunk_id", name="uq_research_evidence_chunk"),
        sa.UniqueConstraint("research_run_id", "label", name="uq_research_evidence_label"),
        sa.UniqueConstraint("research_run_id", "id", name="uq_research_evidence_identity"),
    )


def downgrade() -> None:
    op.drop_table("evidence_items")
    op.drop_table("research_retrieval_results")
