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


def test_evaluation_maps_lower_cosine_distance_to_a_better_run_score(
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

    def fake_retrieve_question(
        db,
        question,
        source_ids,
        settings,
        *,
        top_k,
    ):
        del db, question, source_ids, settings, top_k
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
        "retrieve_question",
        fake_retrieve_question,
    )

    result = retrieval_evaluation.evaluate_dataset(
        RecordingSession(source),
        dataset,
        Settings(azure_openai_embedding_dimensions=3),
    )

    assert result["metrics"]["R@1"] == 1.0
    assert result["metrics"]["RR@5"] == 1.0
    assert result["cases"][0]["first_relevant_rank"] == 1
