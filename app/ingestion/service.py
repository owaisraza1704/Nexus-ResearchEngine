"""Shared document-processing operations for HTTP compatibility and durable local workers."""

from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import ChunkEmbedding, Document, DocumentChunk, Source
from app.embeddings.azure_openai import (
    AzureEmbeddingConfigurationError,
    AzureEmbeddingError,
    AzureEmbeddingTimeoutError,
    embed_texts,
)
from app.errors import NexusError
from app.ingestion.docling_chunker import DocumentChunkingError, chunk_document
from app.ingestion.docling_parser import (
    DocumentHasNoText,
    DocumentParseError,
    mime_type_for_path,
    parse_document,
)


def validate_document(parsed, chunks, settings: Settings) -> None:
    if parsed.page_count is not None and parsed.page_count > settings.max_document_pages:
        raise NexusError("DOCUMENT_TOO_MANY_PAGES", "The document exceeds the page limit.")
    if len(parsed.normalized_text) > settings.max_document_chars:
        raise NexusError("DOCUMENT_TOO_LARGE", "Extracted text exceeds the character limit.")
    if len(chunks) > settings.max_document_chunks:
        raise NexusError("TOO_MANY_CHUNKS", "The document exceeds the chunk limit.")
    if any(len(chunk.text) > settings.max_chunk_chars for chunk in chunks):
        raise NexusError(
            "CHUNK_TOO_LARGE", "A passage exceeds the character limit. Use a smaller document."
        )


def store_document(
    db: Session, source: Source, parsed, chunks, embeddings, *, mime_type: str, metadata: dict
) -> Document:
    document = Document(
        source_id=source.id,
        version=(
            db.scalar(select(func.max(Document.version)).where(Document.source_id == source.id))
            or 0
        )
        + 1,
        status="ready",
        mime_type=mime_type,
        parser_name=parsed.parser_name,
        parser_version=parsed.parser_version,
        normalized_text=parsed.normalized_text,
        normalized_text_sha256=parsed.normalized_text_sha256,
        page_count=parsed.page_count,
        document_metadata={
            "blocks": [
                {"text": block.text, "label": block.label, "locator": block.locator}
                for block in parsed.blocks
            ],
            "chunker_name": "docling.HierarchicalChunker",
            "chunker_version": version("docling-core"),
            "chunk_count": len(chunks),
            **({"conversion": parsed.conversion_metadata} if parsed.conversion_metadata else {}),
            **metadata,
        },
        ready_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.flush()
    stored = [
        DocumentChunk(
            document_id=document.id,
            sequence=chunk.sequence,
            text=chunk.text,
            text_sha256=chunk.text_sha256,
            locator=chunk.locator,
        )
        for chunk in chunks
    ]
    db.add_all(stored)
    db.flush()
    db.add_all(
        [
            ChunkEmbedding(
                chunk_id=chunk.id,
                provider="azure_openai",
                deployment=embedding.deployment,
                model=embedding.model,
                dimensions=len(embedding.vector),
                embedding=list(embedding.vector),
            )
            for chunk, embedding in zip(stored, embeddings, strict=True)
        ]
    )
    source.current_document_id = document.id
    source.status = "ready"
    source.error_code = source.error_detail = None
    db.flush()
    return document


def ingest_source(db: Session, source: Source, path: Path, settings: Settings) -> Document:
    if source.status == "ready" and source.current_document_id:
        return db.get(Document, source.current_document_id)
    started = perf_counter()
    try:
        parsed = parse_document(
            path,
            max_pages=settings.max_document_pages,
            timeout_seconds=settings.ingestion_timeout_seconds,
        )
        chunks = chunk_document(parsed)
        validate_document(parsed, chunks, settings)
        remaining = settings.ingestion_timeout_seconds - (perf_counter() - started)
        if remaining <= 0:
            raise NexusError("INGESTION_TIMEOUT", "The ingestion time limit was exceeded.", 504)
        embeddings = embed_texts(
            [chunk.text for chunk in chunks],
            settings.model_copy(
                update={
                    "provider_timeout_seconds": min(settings.provider_timeout_seconds, remaining)
                }
            ),
        )
        if perf_counter() - started > settings.ingestion_timeout_seconds:
            raise NexusError("INGESTION_TIMEOUT", "The ingestion time limit was exceeded.", 504)
        document = store_document(
            db,
            source,
            parsed,
            chunks,
            embeddings,
            mime_type=mime_type_for_path(path),
            metadata={"ingestion_duration_ms": round((perf_counter() - started) * 1000)},
        )
        db.commit()
        return document
    except DocumentHasNoText as exc:
        error = NexusError("DOCUMENT_HAS_NO_TEXT", str(exc))
    except DocumentParseError as exc:
        error = NexusError("DOCUMENT_PARSE_FAILED", str(exc))
    except DocumentChunkingError as exc:
        error = NexusError("DOCUMENT_CHUNKING_FAILED", str(exc))
    except AzureEmbeddingConfigurationError as exc:
        error = NexusError("EMBEDDING_NOT_CONFIGURED", str(exc), 503)
    except AzureEmbeddingTimeoutError as exc:
        error = NexusError("EMBEDDING_TIMEOUT", str(exc), 504, retryable=True)
    except AzureEmbeddingError as exc:
        error = NexusError("DOCUMENT_EMBEDDING_FAILED", str(exc), 502, retryable=True)
    except NexusError as exc:
        error = exc
    db.rollback()
    source.status, source.error_code, source.error_detail = "failed", error.code, str(error)
    db.commit()
    raise error
