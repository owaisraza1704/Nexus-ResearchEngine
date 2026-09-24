"""Add local research workspaces and durable jobs using Procrastinate 3.10."""

from procrastinate.schema import SchemaManager
from sqlalchemy import text

from alembic import op

revision = "0009_local_research_jobs"
down_revision = "0008_research_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    # The pinned library owns its queue schema. Keep it in the same search_path and
    # transaction as our tables, including isolated integration-test schemas.
    exists = connection.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_tables "
            "WHERE schemaname=current_schema() AND tablename='procrastinate_jobs')"
        )
    )
    if not exists:
        connection.connection.driver_connection.execute(SchemaManager.get_schema())
    op.execute("""
        ALTER TABLE workspaces ADD COLUMN description text NOT NULL DEFAULT '';
        ALTER TABLE workspaces ADD COLUMN draft jsonb NOT NULL DEFAULT '{}';
        ALTER TABLE sources ADD COLUMN artifact_name varchar(128);
        ALTER TABLE sources ADD COLUMN ingestion_job_id bigint;
        ALTER TABLE sources ADD COLUMN ingestion_attempts integer NOT NULL DEFAULT 0;

        CREATE TABLE workspace_sources (
            workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
            source_id uuid REFERENCES sources(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (workspace_id, source_id)
        );
        CREATE TABLE research_jobs (
            id uuid PRIMARY KEY,
            workspace_id uuid NOT NULL REFERENCES workspaces(id),
            run_id uuid NOT NULL UNIQUE REFERENCES research_runs(id),
            question text NOT NULL, mode varchar(32) NOT NULL,
            request_hash varchar(64) NOT NULL, idempotency_key varchar(200),
            status varchar(32) NOT NULL, policy_version varchar(64) NOT NULL,
            policy jsonb NOT NULL, queue_job_id bigint,
            planning_attempts integer NOT NULL, event_sequence integer NOT NULL,
            error_code varchar(64), error_detail text, cancel_requested_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            started_at timestamptz, completed_at timestamptz,
            CONSTRAINT uq_job_request UNIQUE(workspace_id,idempotency_key),
            CONSTRAINT ck_job_status CHECK(status IN (
                'created','planning','planned','running','completed',
                'completed_with_gaps','failed','cancel_requested','cancelled')),
            CONSTRAINT ck_job_mode CHECK(mode IN (
                'answer','comparison','synthesis','evidence','agentic'))
        );
        CREATE INDEX ix_research_jobs_workspace_id ON research_jobs(workspace_id);
        CREATE INDEX ix_research_jobs_created_at ON research_jobs(created_at);
        CREATE INDEX ix_research_jobs_status ON research_jobs(status);
        CREATE TABLE job_budgets (
            job_id uuid PRIMARY KEY REFERENCES research_jobs(id) ON DELETE CASCADE,
            limits jsonb NOT NULL, used_provider_calls integer NOT NULL,
            used_input_tokens integer NOT NULL, used_output_tokens integer NOT NULL,
            reserved_input_tokens integer NOT NULL, reserved_output_tokens integer NOT NULL,
            unknown_usage_calls integer NOT NULL, used_tasks integer NOT NULL
        );
        CREATE TABLE research_plans (
            id uuid PRIMARY KEY,
            job_id uuid NOT NULL UNIQUE REFERENCES research_jobs(id) ON DELETE CASCADE,
            schema_version varchar(32) NOT NULL, status varchar(32) NOT NULL,
            graph_hash varchar(64) NOT NULL, plan_json jsonb NOT NULL,
            planner_provider varchar(200) NOT NULL, prompt_version varchar(64) NOT NULL,
            rejection_code varchar(64), created_at timestamptz NOT NULL DEFAULT now(),
            validated_at timestamptz,
            CONSTRAINT uq_plan_job_identity UNIQUE(job_id,id)
        );
        CREATE TABLE research_tasks (
            id uuid PRIMARY KEY, job_id uuid NOT NULL, plan_id uuid NOT NULL,
            task_key varchar(80) NOT NULL, task_type varchar(40) NOT NULL,
            optional boolean NOT NULL, state varchar(32) NOT NULL,
            input_json jsonb NOT NULL, output_ref jsonb,
            idempotency_key varchar(64) NOT NULL UNIQUE, queue_job_id bigint,
            attempt_count integer NOT NULL, max_attempts integer NOT NULL,
            worker_id varchar(200), error_code varchar(64),
            created_at timestamptz NOT NULL DEFAULT now(),
            started_at timestamptz, completed_at timestamptz,
            FOREIGN KEY(job_id,plan_id) REFERENCES research_plans(job_id,id) ON DELETE CASCADE,
            CONSTRAINT uq_job_task_key UNIQUE(job_id,task_key),
            CONSTRAINT uq_task_job_identity UNIQUE(job_id,id),
            CONSTRAINT ck_task_state CHECK(state IN (
                'pending','ready','running','retry_wait','succeeded','failed','cancelled','skipped'))
        );
        CREATE INDEX ix_research_tasks_job_id ON research_tasks(job_id);
        CREATE TABLE task_dependencies (
            job_id uuid NOT NULL, task_id uuid NOT NULL, depends_on_task_id uuid NOT NULL,
            PRIMARY KEY(task_id,depends_on_task_id),
            FOREIGN KEY(job_id,task_id) REFERENCES research_tasks(job_id,id) ON DELETE CASCADE,
            FOREIGN KEY(job_id,depends_on_task_id)
                REFERENCES research_tasks(job_id,id) ON DELETE CASCADE,
            CONSTRAINT ck_dependency_not_self CHECK(task_id <> depends_on_task_id)
        );
        CREATE TABLE task_attempts (
            id uuid PRIMARY KEY, task_id uuid NOT NULL
                REFERENCES research_tasks(id) ON DELETE CASCADE,
            attempt_number integer NOT NULL, worker_id varchar(200),
            status varchar(32) NOT NULL, error_code varchar(64), provider_usage jsonb NOT NULL,
            started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
            CONSTRAINT uq_task_attempt UNIQUE(task_id,attempt_number)
        );
        CREATE INDEX ix_task_attempts_task_id ON task_attempts(task_id);
        CREATE TABLE job_events (
            id uuid PRIMARY KEY, job_id uuid NOT NULL
                REFERENCES research_jobs(id) ON DELETE CASCADE,
            task_id uuid REFERENCES research_tasks(id), sequence integer NOT NULL,
            event_type varchar(64) NOT NULL, payload jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_job_event_sequence UNIQUE(job_id,sequence)
        );
        CREATE INDEX ix_job_events_job_id ON job_events(job_id);
        CREATE TABLE external_sources (
            id uuid PRIMARY KEY, task_id uuid NOT NULL UNIQUE REFERENCES research_tasks(id),
            source_id uuid NOT NULL REFERENCES sources(id),
            document_id uuid NOT NULL REFERENCES documents(id),
            provider varchar(64) NOT NULL, url text NOT NULL, canonical_url text NOT NULL,
            title text NOT NULL, content_sha256 varchar(64) NOT NULL, metadata jsonb NOT NULL,
            retrieved_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE result_reviews (
            job_id uuid PRIMARY KEY REFERENCES research_jobs(id) ON DELETE CASCADE,
            groundedness integer NOT NULL, relevance integer NOT NULL,
            citation_quality integer NOT NULL, notes text NOT NULL,
            reviewed_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_review_groundedness CHECK(groundedness BETWEEN 1 AND 5),
            CONSTRAINT ck_review_relevance CHECK(relevance BETWEEN 1 AND 5),
            CONSTRAINT ck_review_citations CHECK(citation_quality BETWEEN 1 AND 5)
        );
    """)


def downgrade() -> None:
    if op.get_bind().scalar(
        text("SELECT count(*) FROM procrastinate_jobs WHERE status IN ('todo','doing')")
    ):
        raise RuntimeError("Stop workers and finish or cancel queued jobs before downgrading.")
    for name in (
        "result_reviews",
        "external_sources",
        "job_events",
        "task_attempts",
        "task_dependencies",
        "research_tasks",
        "research_plans",
        "job_budgets",
        "research_jobs",
        "workspace_sources",
    ):
        op.drop_table(name)
    for name in ("artifact_name", "ingestion_job_id", "ingestion_attempts"):
        op.drop_column("sources", name)
    op.drop_column("workspaces", "draft")
    op.drop_column("workspaces", "description")
    # Retain the library's queue/event history; upgrading reuses that schema.
