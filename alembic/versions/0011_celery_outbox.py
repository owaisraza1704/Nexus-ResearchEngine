"""Move pending delivery to Celery while preserving all research and old queue history."""

from sqlalchemy import text

from alembic import op

revision = "0011_celery_outbox"
down_revision = "0010_hybrid_retrieval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE queue_deliveries (
            id bigserial PRIMARY KEY,
            celery_id uuid NOT NULL UNIQUE,
            task_name varchar(64) NOT NULL,
            args jsonb NOT NULL,
            lock_key varchar(200) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            published_at timestamptz,
            finished_at timestamptz,
            cancelled_at timestamptz
        );
        CREATE INDEX ix_queue_deliveries_pending ON queue_deliveries(published_at, id)
            WHERE finished_at IS NULL AND cancelled_at IS NULL;

        INSERT INTO queue_deliveries(id, celery_id, task_name, args, lock_key, created_at)
        SELECT id, gen_random_uuid(), task_name, args, lock, COALESCE(scheduled_at, now())
        FROM procrastinate_jobs
        WHERE status IN ('todo', 'doing')
            AND task_name IN ('nexus.plan', 'nexus.execute', 'nexus.ingest');

        SELECT setval('queue_deliveries_id_seq',
            COALESCE((SELECT max(id) FROM procrastinate_jobs), 0) + 1, false);
    """)


def downgrade() -> None:
    if op.get_bind().scalar(
        text(
            "SELECT count(*) FROM queue_deliveries "
            "WHERE finished_at IS NULL AND cancelled_at IS NULL"
        )
    ):
        raise RuntimeError("Finish or cancel accepted Celery work before downgrading.")
    op.drop_table("queue_deliveries")
