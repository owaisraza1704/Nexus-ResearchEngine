from types import SimpleNamespace

from evals import retrieval


def test_retrieval_evaluation_scores_the_selected_strategy(monkeypatch):
    source = SimpleNamespace(id="source", current_document_id="document")
    db = SimpleNamespace(scalar=lambda statement: source)
    dataset = retrieval.RetrievalDataset(
        source_content_sha256="source-hash",
        cases=(retrieval.RetrievalCase("case", "Find the relevant passage", (2,)),),
    )
    monkeypatch.setattr(
        retrieval,
        "embed_text",
        lambda question, settings: SimpleNamespace(vector=(1.0,)),
    )

    def search(db, vector, source_ids, settings, *, strategy, question, top_k):
        assert vector == (1.0,) and source_ids == ("source",) and top_k == 5
        assert question == (dataset.cases[0].question if strategy == "hybrid" else None)
        sequences = (1, 2) if strategy == "vector" else (2, 1)
        return tuple(
            SimpleNamespace(sequence=sequence, cosine_distance=float(sequence))
            for sequence in sequences
        )

    monkeypatch.setattr(retrieval, "search_chunks", search)

    vector = retrieval.evaluate_dataset(db, dataset, object(), "vector")
    hybrid = retrieval.evaluate_dataset(db, dataset, object(), "hybrid")

    assert vector["cases"][0]["first_relevant_rank"] == 2
    assert hybrid["cases"][0]["first_relevant_rank"] == 1
    assert hybrid["metrics"]["RR@5"] > vector["metrics"]["RR@5"]
