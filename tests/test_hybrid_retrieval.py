from sqlalchemy import select

from app.db.models import ChunkEmbedding, Document
from app.retrieval.vector_search import search_chunks


def test_keyword_match_promotes_a_passage_and_preserves_scores(db, settings, ready_source):
    source, document, chunks = ready_source(
        (
            "A general overview of the system.",
            "The ZXQ741 protocol requires explicit consent.",
        )
    )
    options = dict(top_k=1, document_id=document.id, embedding_model="text-embedding-3-large")
    vector = [1.0] + [0.0] * 3071
    dense = search_chunks(db, vector, [source.id], settings, **options)
    hybrid = search_chunks(
        db,
        vector,
        [source.id],
        settings,
        strategy="hybrid",
        question="ZXQ741",
        **options,
    )
    assert dense[0].chunk_id == chunks[0].id
    assert hybrid[0].chunk_id == chunks[1].id
    assert hybrid[0].fusion_score > 0
    assert hybrid[0].lexical_score > 0
    assert hybrid[0].cosine_distance > dense[0].cosine_distance


def test_hybrid_uses_same_pinned_source_and_embedding_scope(db, settings, ready_source):
    source, document, chunks = ready_source(("ZXQ741 source evidence.",))
    ready_source(("ZXQ741 ZXQ741 ZXQ741 unselected material.",))
    newer = Document(
        source_id=source.id,
        version=2,
        status="parsing",
        mime_type="application/pdf",
        parser_name="docling",
        parser_version="test",
    )
    db.add(newer)
    db.flush()
    source.current_document_id = newer.id
    source.status = "processing"
    db.commit()
    options = dict(
        document_id=document.id,
        embedding_model="text-embedding-3-large",
        strategy="hybrid",
        question="ZXQ741",
    )
    results = search_chunks(db, [1.0] * 3072, [source.id], settings, **options)
    assert [item.chunk_id for item in results] == [chunks[0].id]
    embedding = db.scalar(select(ChunkEmbedding).where(ChunkEmbedding.chunk_id == chunks[0].id))
    embedding.model = "incompatible-model"
    db.commit()
    assert search_chunks(db, [1.0] * 3072, [source.id], settings, **options) == ()


def test_no_keyword_match_retains_vector_order(db, settings, ready_source):
    source, _, chunks = ready_source()
    results = search_chunks(
        db,
        [1.0] + [0.0] * 3071,
        [source.id],
        settings,
        strategy="hybrid",
        question="nomatch741",
    )
    assert [item.chunk_id for item in results] == [chunk.id for chunk in chunks]
    assert all(item.fusion_score is not None and item.lexical_score is None for item in results)


def test_keyword_index_updates_when_chunks_are_inserted(db, settings, ready_source):
    source, _, _ = ready_source(("Retention requirements are searchable immediately.",))
    assert (
        search_chunks(
            db,
            [1.0] * 3072,
            [source.id],
            settings,
            strategy="hybrid",
            question="retention",
        )[0].lexical_score
        > 0
    )


def test_natural_question_does_not_require_every_keyword_in_one_passage(db, settings, ready_source):
    source, _, _ = ready_source(("Alpha retains records for thirty days.",))
    result = search_chunks(
        db,
        [1.0] * 3072,
        [source.id],
        settings,
        strategy="hybrid",
        question="What are Alpha retention requirements and audit procedures?",
    )
    assert result[0].lexical_score > 0
