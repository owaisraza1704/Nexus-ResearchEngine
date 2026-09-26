from types import SimpleNamespace
from uuid import uuid4

from app.config import Settings
from app.retrieval.vector_search import RetrievedChunk
from evals import retrieval as retrieval_evaluation


class RecordingSession:
    def __init__(self, source) -> None:
        self.source = source

    def scalar(self, statement):
        del statement
        return self.source


def test_evaluation_uses_vector_search_order_for_metrics(
    monkeypatch,
) -> None:
    source_id = uuid4()
    source = SimpleNamespace(id=source_id, current_document_id=uuid4())
    dataset = retrieval_evaluation.RetrievalDataset(
        source_content_sha256="source-hash",
        cases=(
            retrieval_evaluation.RetrievalCase(
                case_id="objective",
                question="What is the objective?",
                relevant_sequences=(2,),
            ),
        ),
    )

    monkeypatch.setattr(
        retrieval_evaluation,
        "embed_text",
        lambda question, settings: SimpleNamespace(vector=(1.0, 0.0, 0.0)),
    )

    def fake_search_chunks(
        db,
        query_vector,
        source_ids,
        settings,
        *,
        top_k,
        strategy,
        question,
    ):
        assert query_vector == (1.0, 0.0, 0.0)
        assert strategy == "vector" and question is None
        del db, source_ids, settings, top_k
        return (
            RetrievedChunk(
                chunk_id=uuid4(),
                document_id=source.current_document_id,
                source_id=source_id,
                sequence=2,
                text="Relevant",
                locator={},
                cosine_distance=0.1,
            ),
            RetrievedChunk(
                chunk_id=uuid4(),
                document_id=source.current_document_id,
                source_id=source_id,
                sequence=8,
                text="Less relevant",
                locator={},
                cosine_distance=0.4,
            ),
        )

    monkeypatch.setattr(
        retrieval_evaluation,
        "search_chunks",
        fake_search_chunks,
    )

    result = retrieval_evaluation.evaluate_dataset(
        RecordingSession(source),
        dataset,
        Settings(azure_openai_embedding_dimensions=3),
    )

    assert result["metrics"]["R@1"] == 1.0
    assert result["metrics"]["RR@5"] == 1.0
    assert result["cases"][0]["first_relevant_rank"] == 1
