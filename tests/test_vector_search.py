from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.config import Settings
from app.db.models import ChunkEmbedding
from app.embeddings.azure_openai import EmbeddingResult
from app.retrieval import vector_search
from app.retrieval.vector_search import RetrievedChunk, search_chunks


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


def test_search_chunks_passes_a_pgvector_compatible_query_vector() -> None:
    db = RecordingSession()

    search_chunks(
        db,
        query_vector=(0.1, 0.2, 0.3),
        source_ids=(uuid4(),),
        settings=_settings(),
    )

    compiled = db.statement.compile(dialect=postgresql.dialect())
    query_vector = compiled.params["embedding_1"]
    processor = ChunkEmbedding.__table__.c.embedding.type.bind_processor(
        postgresql.dialect()
    )

    assert isinstance(query_vector, list)
    assert processor is not None
    assert processor(query_vector) == "[0.1,0.2,0.3]"


def test_retrieve_question_embeds_text_before_searching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_id = uuid4()
    settings = _settings()
    database = RecordingSession()
    embedding = EmbeddingResult(
        vector=(0.1, 0.2, 0.3),
        model="embedding-large",
        deployment="embedding-large",
        prompt_tokens=5,
    )
    retrieved = (
        RetrievedChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_id=source_id,
            sequence=0,
            text="Relevant chunk",
            locator={"page": 1},
            cosine_distance=0.2,
        ),
    )
    calls: dict[str, object] = {}

    def fake_embed_text(value: str, value_settings: Settings) -> EmbeddingResult:
        calls["question"] = value
        calls["embedding_settings"] = value_settings
        return embedding

    def fake_search_chunks(
        value_db,
        query_vector,
        value_source_ids,
        value_settings,
        *,
        top_k: int,
    ) -> tuple[RetrievedChunk, ...]:
        calls["db"] = value_db
        calls["query_vector"] = query_vector
        calls["source_ids"] = value_source_ids
        calls["search_settings"] = value_settings
        calls["top_k"] = top_k
        return retrieved

    monkeypatch.setattr(vector_search, "embed_text", fake_embed_text)
    monkeypatch.setattr(vector_search, "search_chunks", fake_search_chunks)

    results = vector_search.retrieve_question(
        database,
        "What is the project objective?",
        (source_id,),
        settings,
        top_k=3,
    )

    assert results == retrieved
    assert calls == {
        "question": "What is the project objective?",
        "embedding_settings": settings,
        "db": database,
        "query_vector": embedding.vector,
        "source_ids": (source_id,),
        "search_settings": settings,
        "top_k": 3,
    }
