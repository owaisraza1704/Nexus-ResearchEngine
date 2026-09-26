from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ir_measures import RR, Qrel, R, ScoredDoc, calc, nDCG
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Source
from app.db.session import SessionLocal
from app.embeddings.azure_openai import embed_text
from app.retrieval.vector_search import search_chunks

TOP_K = 5
METRICS = (R@1, R@3, R@5, RR@5, nDCG@5)
DEFAULT_CASES_PATH = Path(__file__).with_name("retrieval_cases.json")


@dataclass(frozen=True)
class RetrievalCase:
    case_id: str
    question: str
    relevant_sequences: tuple[int, ...]


@dataclass(frozen=True)
class RetrievalDataset:
    source_content_sha256: str
    cases: tuple[RetrievalCase, ...]


def load_dataset(path: Path) -> RetrievalDataset:
    payload = json.loads(path.read_text())
    cases = tuple(
        RetrievalCase(
            case_id=case["id"],
            question=case["question"],
            relevant_sequences=tuple(case["relevant_sequences"]),
        )
        for case in payload["cases"]
    )
    return RetrievalDataset(
        source_content_sha256=payload["source_content_sha256"],
        cases=cases,
    )


def _chunk_key(source_content_sha256: str, sequence: int) -> str:
    return f"{source_content_sha256}:{sequence}"


def evaluate_dataset(
    db: Session,
    dataset: RetrievalDataset,
    settings: Settings,
    strategy: Literal["vector", "hybrid"] = "vector",
) -> dict[str, Any]:
    source = db.scalar(
        select(Source).where(Source.content_sha256 == dataset.source_content_sha256)
    )
    if source is None:
        raise RuntimeError(
            "No source found for evaluation dataset: "
            f"{dataset.source_content_sha256}"
        )
    if source.current_document_id is None:
        raise RuntimeError("The evaluation source has no current document")

    qrels: list[Qrel] = []
    run: list[ScoredDoc] = []
    case_results: list[dict[str, Any]] = []

    for case in dataset.cases:
        qrels.extend(
            Qrel(
                case.case_id,
                _chunk_key(dataset.source_content_sha256, sequence),
                1,
            )
            for sequence in case.relevant_sequences
        )
        embedding = embed_text(case.question, settings)
        retrieved = search_chunks(
            db,
            embedding.vector,
            (source.id,),
            settings,
            top_k=TOP_K,
            strategy=strategy,
            question=case.question if strategy == "hybrid" else None,
        )
        run.extend(
            ScoredDoc(
                case.case_id,
                _chunk_key(dataset.source_content_sha256, chunk.sequence),
                float(len(retrieved) - rank),
            )
            for rank, chunk in enumerate(retrieved)
        )
        retrieved_sequences = [chunk.sequence for chunk in retrieved]
        case_results.append(
            {
                "id": case.case_id,
                "relevant_sequences": list(case.relevant_sequences),
                "retrieved_sequences": retrieved_sequences,
                "first_relevant_rank": next(
                    (
                        rank
                        for rank, sequence in enumerate(retrieved_sequences, start=1)
                        if sequence in case.relevant_sequences
                    ),
                    None,
                ),
            }
        )

    calculated = calc(METRICS, qrels, run)
    return {
        "strategy": strategy,
        "source_content_sha256": dataset.source_content_sha256,
        "case_count": len(dataset.cases),
        "top_k": TOP_K,
        "metrics": {
            str(metric): float(value) for metric, value in calculated.aggregated.items()
        },
        "cases": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate labeled retrieval cases")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--strategy", choices=("vector", "hybrid"), default="vector")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    dataset = load_dataset(args.cases)
    with SessionLocal() as db:
        result = evaluate_dataset(db, dataset, get_settings(), args.strategy)
    report = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
    print(report, end="")


if __name__ == "__main__":
    main()
