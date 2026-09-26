from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from alembic import command
from app.db.job_models import QueueDelivery
from app.db.models import Answer, AnswerCitation, Query, RetrievalResult
from app.db.research_models import (
    Claim,
    ClaimEvidence,
    EvidenceItem,
    ResearchGap,
    ResearchResult,
    ResearchRetrievalResult,
    ResearchRun,
    ResearchRunSource,
    ResultCitation,
    SourceCoverage,
)


def test_fresh_migrations_create_answer_schema(db, migrated_database):
    _, schema = migrated_database
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == head
    inspector = inspect(db.connection())
    for model in (Query, RetrievalResult, Answer, AnswerCitation):
        columns = inspector.get_columns(model.__tablename__, schema=schema)
        assert {column["name"] for column in columns} == set(model.__table__.columns.keys())
    foreign_keys = inspector.get_foreign_keys("answer_citations", schema=schema)
    assert {key["referred_table"] for key in foreign_keys} == {"answers", "retrieval_results"}


def test_fresh_migrations_match_all_research_models(db, migrated_database):
    _, schema = migrated_database
    inspector = inspect(db.connection())
    for model in (
        ResearchRun,
        ResearchRunSource,
        SourceCoverage,
        ResearchRetrievalResult,
        EvidenceItem,
        Claim,
        ClaimEvidence,
        ResearchGap,
        ResearchResult,
        ResultCitation,
    ):
        columns = inspector.get_columns(model.__tablename__, schema=schema)
        assert {column["name"] for column in columns} == set(model.__table__.columns.keys())
    foreign_keys = inspector.get_foreign_keys("claim_evidence", schema=schema)
    assert all(len(key["constrained_columns"]) == 2 for key in foreign_keys)


def test_upgrade_indexes_existing_chunks_and_preserves_pending_delivery_ids(
    db,
    migrated_database,
    ready_source,
):
    _, schema = migrated_database
    _, _, chunks = ready_source(("Existing retention evidence.",))
    config = Config("alembic.ini")
    config.attributes["connection"] = db.connection()
    config.attributes["version_table_schema"] = schema
    command.downgrade(config, "0009_local_research_jobs")
    identity = db.scalar(
        text("""
        INSERT INTO procrastinate_jobs(queue_name, task_name, args, lock)
        VALUES ('nexus', 'nexus.plan', '{"job_id":"pending-test"}', 'plan:pending-test')
        RETURNING id
    """)
    )
    command.upgrade(config, "head")
    delivery = db.get(QueueDelivery, identity)
    assert delivery.args == {"job_id": "pending-test"}
    assert delivery.created_at is not None and delivery.finished_at is None
    assert db.scalar(
        text(
            "SELECT search_vector @@ plainto_tsquery('english', 'retention') "
            "FROM document_chunks WHERE id=:id"
        ),
        {"id": chunks[0].id},
    )
    assert db.scalar(text("SELECT count(*) FROM chunk_embeddings")) == 1
