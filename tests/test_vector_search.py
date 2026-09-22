from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.config import Settings
from app.retrieval.vector_search import search_chunks


class RecordingSession:
    def __init__(self, rows: tuple[SimpleNamespace, ...] = ()) -> None:
        self.rows = rows
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return SimpleNamespace(all=lambda: self.rows)


def _settings() -> Settings:
    return Settings(
        azure_openai_embedding_deployment="embedding-large",
        azure_openai_embedding_dimensions=3,
    )


def test_search_chunks_maps_ranked_rows_and_scopes_the_query() -> None:
    source_id = uuid4()
    document_id = uuid4()
    rows = (
        SimpleNamespace(
            chunk_id=uuid4(),
            document_id=document_id,
            source_id=source_id,
            sequence=4,
            text="Most relevant",
            locator={"page": 2},
            cosine_distance=0.1,
        ),
        SimpleNamespace(
            chunk_id=uuid4(),
            document_id=document_id,
            source_id=source_id,
            sequence=9,
            text="Next relevant",
            locator={"page": 3},
            cosine_distance=0.3,
        ),
    )
    db = RecordingSession(rows)

    results = search_chunks(
        db,
        query_vector=(0.1, 0.2, 0.3),
        source_ids=(source_id,),
        settings=_settings(),
        top_k=2,
    )

    assert [result.text for result in results] == ["Most relevant", "Next relevant"]
    assert [result.cosine_distance for result in results] == [0.1, 0.3]
    assert results[0].source_id == source_id
    assert results[0].locator == {"page": 2}

    compiled = str(db.statement.compile(dialect=postgresql.dialect()))
    assert "sources.id IN" in compiled
    assert "sources.current_document_id = documents.id" in compiled
    assert "documents.status = " in compiled
    assert "chunk_embeddings.embedding <=> " in compiled
    assert " LIMIT " in compiled


def test_search_chunks_returns_empty_for_empty_source_scope() -> None:
    db = RecordingSession()

    results = search_chunks(
        db,
        query_vector=(0.1, 0.2, 0.3),
        source_ids=(),
        settings=_settings(),
    )

    assert results == ()
    assert db.statement is None


def test_search_chunks_rejects_invalid_top_k() -> None:
    with pytest.raises(ValueError, match="top_k"):
        search_chunks(
            RecordingSession(),
            query_vector=(0.1, 0.2, 0.3),
            source_ids=(uuid4(),),
            settings=_settings(),
            top_k=0,
        )


def test_search_chunks_rejects_unexpected_query_dimensions() -> None:
    with pytest.raises(ValueError, match="unexpected dimension"):
        search_chunks(
            RecordingSession(),
            query_vector=(0.1, 0.2),
            source_ids=(uuid4(),),
            settings=_settings(),
        )
