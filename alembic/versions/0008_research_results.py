"""Store validated research claims, evidence relationships, gaps, and results."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008_research_results"
down_revision = "0007_research_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("research_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(32), nullable=False),
        sa.Column("support_status", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("research_run_id", "sequence", name="uq_research_claim_sequence"),
        sa.UniqueConstraint("research_run_id", "id", name="uq_research_claim_identity"),
        sa.CheckConstraint(
            "support_status IN ('supported', 'partially_supported', 'contradicted', 'unresolved')",
            name="ck_claim_support_status",
        ),
    )
    op.create_table(
        "claim_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("research_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship", sa.String(32), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["research_run_id", "claim_id"],
            ["claims.research_run_id", "claims.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["research_run_id", "evidence_item_id"],
            ["evidence_items.research_run_id", "evidence_items.id"],
        ),
        sa.UniqueConstraint(
            "claim_id", "evidence_item_id", "relationship", name="uq_claim_evidence"
        ),
        sa.CheckConstraint(
            "relationship IN ('supports', 'contradicts', 'qualifies', 'context')",
            name="ck_claim_evidence_relationship",
        ),
    )
    op.create_table(
        "research_gaps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("research_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("gap_text", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("research_run_id", "sequence", name="uq_research_gap_sequence"),
    )
    op.create_table(
        "research_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("research_run_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("limitation", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("research_run_id", "id", name="uq_research_result_identity"),
        sa.CheckConstraint(
            "status IN ('completed', 'insufficient_context')", name="ck_research_result_status"
        ),
    )
    op.create_table(
        "result_citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("research_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(16), nullable=False),
        sa.Column("display_text", sa.Text(), nullable=False),
        sa.Column("locator_snapshot", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_run_id", "research_result_id"],
            ["research_results.research_run_id", "research_results.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["research_run_id", "evidence_item_id"],
            ["evidence_items.research_run_id", "evidence_items.id"],
        ),
        sa.UniqueConstraint("research_result_id", "label", name="uq_research_citation_label"),
    )


def downgrade() -> None:
    op.drop_table("result_citations")
    op.drop_table("research_results")
    op.drop_table("research_gaps")
    op.drop_table("claim_evidence")
    op.drop_table("claims")
