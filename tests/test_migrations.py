from sqlalchemy import inspect, text

from app.db.models import Answer, AnswerCitation, Query, RetrievalResult


def test_fresh_migrations_create_answer_schema(db, migrated_database):
    _, schema = migrated_database
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0005_query_answers"
    inspector = inspect(db.connection())
    for model in (Query, RetrievalResult, Answer, AnswerCitation):
        columns = inspector.get_columns(model.__tablename__, schema=schema)
        assert {column["name"] for column in columns} == set(model.__table__.columns.keys())
    foreign_keys = inspector.get_foreign_keys("answer_citations", schema=schema)
    assert {key["referred_table"] for key in foreign_keys} == {"answers", "retrieval_results"}
