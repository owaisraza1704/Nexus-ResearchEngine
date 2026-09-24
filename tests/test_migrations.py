from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

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
