"""Approved task implementations. Parsing, search, synthesis, and validators are reused."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from time import perf_counter
from uuid import UUID, uuid4

from docling_core.types.doc import DocItemLabel, DoclingDocument
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.db.job_models import ExternalSource, ResearchTask, WorkspaceSource
from app.db.models import Document, DocumentChunk, Source
from app.db.research_models import (
    ResearchGap,
    ResearchResult,
    ResearchRun,
    ResearchRunSource,
    ResultCitation,
    SourceCoverage,
)
from app.errors import NexusError
from app.ingestion.docling_chunker import ChunkDraft, chunk_document
from app.ingestion.docling_parser import normalize_document
from app.ingestion.service import store_document, validate_document
from app.jobs.providers import embed_for_job, generate_for_job
from app.jobs.state import locked_job
from app.jobs.web import fetch_public_page
from app.research.results import evidence_rows, save_result
from app.research.retrieval import store_source_evidence
from app.research.synthesis import (
    RESEARCH_INSTRUCTIONS,
    GeneratedGap,
    GeneratedResearch,
    build_prompt,
)
from app.retrieval.vector_search import RetrievedChunk, search_chunks


def acquire_web(db, job, task, attempt, settings) -> dict:
    existing = db.scalar(select(ExternalSource).where(ExternalSource.task_id == task.id))
    if existing:
        return {"external_source_id": str(existing.id), "source_id": str(existing.source_id)}
    url = job.policy["web_urls"][task.input_json["url_index"]]
    snapshot = asyncio.run(fetch_public_page(url, job.policy["allowed_domains"], settings))
    native = DoclingDocument(name=snapshot.title)
    for paragraph in snapshot.text.splitlines():
        if paragraph.strip():
            native.add_text(label=DocItemLabel.TEXT, text=paragraph.strip())
    parsed = replace(
        normalize_document(native), parser_name="trafilatura", parser_version=version("trafilatura")
    )
    retrieved_at = datetime.now(timezone.utc)
    provenance = {
        "url": snapshot.url,
        "canonical_url": snapshot.final_url,
        "retrieved_at": retrieved_at.isoformat(),
        "content_sha256": snapshot.content_sha256,
        "provider": "approved_url",
    }
    chunks = tuple(
        ChunkDraft(chunk.sequence, chunk.text, {**chunk.locator, **provenance})
        for chunk in chunk_document(parsed)
    )
    validate_document(parsed, chunks, settings)
    embeddings = embed_for_job(
        db, job.id, [chunk.text for chunk in chunks], settings, task=task, attempt=attempt
    )
    # URL + fetched bytes distinguish independent provenance even for identical page text.
    identity = sha256((url + snapshot.content_sha256).encode()).hexdigest()
    job = locked_job(db, job.id)
    db.execute(
        insert(Source)
        .values(
            id=uuid4(),
            display_name=snapshot.title,
            original_filename=snapshot.title[:245] + ".html",
            kind="web",
            status="registered",
            content_sha256=identity,
        )
        .on_conflict_do_nothing(index_elements=["content_sha256"])
    )
    source = db.scalar(select(Source).where(Source.content_sha256 == identity).with_for_update())
    if source.current_document_id:
        document = db.get(Document, source.current_document_id)
    else:
        document = store_document(
            db,
            source,
            parsed,
            chunks,
            embeddings,
            mime_type="text/html",
            metadata={**provenance, "original_content_type": snapshot.content_type},
        )
    db.execute(
        insert(WorkspaceSource)
        .values(workspace_id=job.workspace_id, source_id=source.id)
        .on_conflict_do_nothing()
    )
    external = ExternalSource(
        task_id=task.id,
        source_id=source.id,
        document_id=document.id,
        url=url,
        canonical_url=snapshot.final_url,
        title=snapshot.title,
        content_sha256=snapshot.content_sha256,
        source_metadata=provenance,
        retrieved_at=retrieved_at,
    )
    db.add(external)
    pin = db.scalar(
        select(ResearchRunSource).where(
            ResearchRunSource.research_run_id == job.run_id,
            ResearchRunSource.source_id == source.id,
        )
    )
    if pin is None:
        order = (
            db.scalar(
                select(func.max(ResearchRunSource.source_order)).where(
                    ResearchRunSource.research_run_id == job.run_id
                )
            )
            or 0
        ) + 1
        pin = ResearchRunSource(
            research_run_id=job.run_id,
            source_id=source.id,
            document_id=document.id,
            document_version=document.version,
            source_order=order,
            display_name=source.display_name,
        )
        db.add(pin)
        db.flush()
        db.add(SourceCoverage(research_run_id=job.run_id, research_run_source_id=pin.id))
    db.flush()
    return {
        "external_source_id": str(external.id),
        "source_id": str(source.id),
        "document_id": str(document.id),
    }


def retrieve(db, job, task, attempt, settings) -> dict:
    run = db.get(ResearchRun, job.run_id)
    embedding = embed_for_job(
        db, job.id, [task.input_json["question"]], settings, task=task, attempt=attempt
    )[0]
    pins = db.scalars(
        select(ResearchRunSource)
        .where(ResearchRunSource.research_run_id == run.id)
        .order_by(ResearchRunSource.source_order)
    ).all()
    candidates = []
    started = perf_counter()
    for pin in pins:
        db.execute(
            text("SELECT set_config('statement_timeout', :value, true)"),
            {"value": str(int(settings.provider_timeout_seconds * 1000))},
        )
        if db.get(Document, pin.document_id) is None:
            raise NexusError("SOURCE_VERSION_UNAVAILABLE", "A pinned snapshot is unavailable.", 409)
        chunks = search_chunks(
            db,
            embedding.vector,
            [pin.source_id],
            settings,
            top_k=run.retrieval_config["top_k_per_source"],
            document_id=pin.document_id,
            embedding_model=embedding.model,
            strategy=run.retrieval_config.get("strategy", "vector"),
            question=task.input_json["question"],
        )
        candidates.extend(
            {
                "chunk_id": str(chunk.chunk_id),
                "document_id": str(chunk.document_id),
                "source_id": str(chunk.source_id),
                "cosine_distance": chunk.cosine_distance,
                "fusion_score": chunk.fusion_score,
                "lexical_score": chunk.lexical_score,
            }
            for chunk in chunks
        )
    return {
        "candidates": candidates,
        "embedding_tokens": embedding.prompt_tokens,
        "embedding_model": embedding.model,
        "duration_ms": round((perf_counter() - started) * 1000),
    }


def extract_evidence(db, job, task, attempt, settings) -> dict:
    run = db.get(ResearchRun, job.run_id)
    hybrid = run.retrieval_config.get("strategy") == "hybrid"
    branches = db.scalars(
        select(ResearchTask)
        .where(
            ResearchTask.job_id == job.id,
            ResearchTask.task_type == "retrieve_internal",
            ResearchTask.state == "succeeded",
        )
        .order_by(ResearchTask.task_key)
    ).all()
    candidates = {}
    for branch in branches:
        for candidate in branch.output_ref["candidates"]:
            previous = candidates.get(candidate["chunk_id"])
            if previous is None:
                candidates[candidate["chunk_id"]] = candidate
                continue
            if hybrid:
                better = (candidate.get("fusion_score") or 0) > (previous.get("fusion_score") or 0)
            else:
                better = candidate["cosine_distance"] < previous["cosine_distance"]
            if better:
                candidates[candidate["chunk_id"]] = candidate
    pins = db.execute(
        select(ResearchRunSource, SourceCoverage)
        .join(SourceCoverage, SourceCoverage.research_run_source_id == ResearchRunSource.id)
        .where(ResearchRunSource.research_run_id == run.id)
        .order_by(ResearchRunSource.source_order)
    ).all()
    evidence = []
    run.status = "retrieving"
    for pin, coverage in pins:
        chunks = []
        for candidate in candidates.values():
            if candidate["source_id"] != str(pin.source_id):
                continue
            chunk = db.get(DocumentChunk, UUID(candidate["chunk_id"]))
            if chunk is None or chunk.document_id != pin.document_id:
                raise NexusError(
                    "EVIDENCE_VALIDATION_FAILED", "A candidate is outside its pinned source.", 502
                )
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    source_id=pin.source_id,
                    sequence=chunk.sequence,
                    text=chunk.text,
                    locator=chunk.locator,
                    cosine_distance=candidate["cosine_distance"],
                    fusion_score=candidate.get("fusion_score"),
                    lexical_score=candidate.get("lexical_score"),
                )
            )
        chunks.sort(key=lambda chunk: (
            -(chunk.fusion_score or 0) if hybrid else chunk.cosine_distance,
            chunk.sequence, str(chunk.chunk_id),
        ))
        evidence.extend(
            store_source_evidence(
                db,
                run,
                pin,
                coverage,
                chunks,
                char_limit=run.retrieval_config["max_context_chars"] // len(pins),
                item_limit=run.retrieval_config["max_evidence"] // len(pins),
                label_offset=len(evidence),
            )
        )
    run.embedding_tokens = sum(
        branch.output_ref.get("embedding_tokens") or 0 for branch in branches
    )
    run.retrieval_ms = sum(branch.output_ref.get("duration_ms", 0) for branch in branches)
    run.retrieval_config = {
        **run.retrieval_config,
        "selected_chunk_count": len(evidence),
        "context_chars": sum(len(item.excerpt) for item in evidence),
        "query_count": len(branches),
        "metric": "rrf" if hybrid else "cosine_distance",
    }
    db.flush()
    return {"run_id": str(run.id), "evidence_count": len(evidence)}


def synthesize(db, job, task, attempt, settings) -> dict:
    run = db.get(ResearchRun, job.run_id)
    rows = evidence_rows(db, run.id)
    if not rows:
        generated = GeneratedResearch(
            status="insufficient_context",
            summary="No usable passages were available.",
            limitation=(
                "No usable passages were available within the selected sources and context budget."
            ),
            relevant_evidence_ids=[],
            claims=[],
            gaps=[
                GeneratedGap(text="More relevant source evidence is needed.", reason="no_evidence")
            ],
        )
        return {"generated": generated.model_dump(), "duration_ms": 0, "model": None}
    if any(
        item.excerpt != chunk.text or item.locator_snapshot != chunk.locator
        for item, _, _, chunk, _ in rows
    ):
        raise NexusError(
            "EVIDENCE_VALIDATION_FAILED", "Stored excerpts do not match their snapshots.", 502
        )
    instructions = RESEARCH_INSTRUCTIONS
    if run.answer_config["min_cited_sources"] == 1:
        instructions = instructions.replace("at least two sources", "at least one source")
    started = perf_counter()
    output = generate_for_job(
        db,
        job.id,
        build_prompt(db, run),
        GeneratedResearch,
        settings,
        instructions=instructions,
        max_tokens=run.answer_config["max_output_tokens"],
        task=task,
        attempt=attempt,
    )
    return {
        "generated": output.parsed.model_dump(),
        "model": output.model,
        "input_tokens": output.prompt_tokens,
        "output_tokens": output.completion_tokens,
        "duration_ms": round((perf_counter() - started) * 1000),
    }


def validate_result(db, job, task, attempt, settings) -> dict:
    run = db.get(ResearchRun, job.run_id)
    existing = db.scalar(select(ResearchResult).where(ResearchResult.research_run_id == run.id))
    if existing:
        return {"result_id": str(existing.id)}
    elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
    started = perf_counter() - elapsed
    if job.mode == "evidence":
        rows = evidence_rows(db, run.id)
        if any(
            item.excerpt != chunk.text or item.locator_snapshot != chunk.locator
            for item, _, _, chunk, _ in rows
        ):
            raise NexusError(
                "EVIDENCE_VALIDATION_FAILED", "A passage does not match its snapshot.", 502
            )
        result = ResearchResult(
            research_run_id=run.id,
            status="completed" if rows else "insufficient_context",
            summary=(
                f"Retrieved {len(rows)} candidate passages. "
                "No answer or relevance judgment was generated."
            ),
            limitation=None if rows else "No passages fit the source and context selection.",
            duration_ms=round(elapsed * 1000),
        )
        db.add(result)
        db.flush()
        for item, _, _, _, _ in rows:
            item.used = True
            db.add(
                ResultCitation(
                    research_run_id=run.id,
                    research_result_id=result.id,
                    evidence_item_id=item.id,
                    label=item.label,
                    display_text=item.display_text,
                    locator_snapshot=item.locator_snapshot,
                )
            )
        run.status, run.completed_at = result.status, datetime.now(timezone.utc)
        run.duration_ms = result.duration_ms
    else:
        synthesis = db.scalar(
            select(ResearchTask).where(
                ResearchTask.job_id == job.id,
                ResearchTask.task_type == "synthesize",
                ResearchTask.state == "succeeded",
            )
        )
        output = synthesis.output_ref
        run.status = "synthesizing"
        run.llm_model = output.get("model")
        run.input_tokens, run.output_tokens = (
            output.get("input_tokens"),
            output.get("output_tokens"),
        )
        run.synthesis_ms = output["duration_ms"]
        result = save_result(
            db, run, GeneratedResearch.model_validate(output["generated"]), started, commit=False
        )
    failed_web = db.scalars(
        select(ResearchTask).where(
            ResearchTask.job_id == job.id,
            ResearchTask.optional.is_(True),
            ResearchTask.state == "failed",
        )
    ).all()
    sequence = (
        db.scalar(
            select(func.max(ResearchGap.sequence)).where(ResearchGap.research_run_id == run.id)
        )
        or 0
    )
    for failed in failed_web:
        sequence += 1
        db.add(
            ResearchGap(
                research_run_id=run.id,
                sequence=sequence,
                reason="source_unavailable",
                gap_text=(
                    f"Approved web source {failed.input_json['url_index'] + 1} "
                    f"was unavailable ({failed.error_code})."
                ),
            )
        )
    db.flush()
    return {"result_id": str(result.id)}


HANDLERS = {
    "fetch_web": acquire_web,
    "retrieve_internal": retrieve,
    "extract_evidence": extract_evidence,
    "synthesize": synthesize,
    "validate_result": validate_result,
}
