from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Document, DocumentChunk, Source
from app.db.session import get_db
from app.errors import NexusError
from app.ingestion.artifacts import store_artifact
from app.ingestion.docling_parser import (
    UnsupportedDocumentType,
    mime_type_for_path,
)
from app.ingestion.service import ingest_source

router = APIRouter(prefix="/v1/sources", tags=["sources"])


class DocumentSummary(BaseModel):
    document_id: UUID
    version: int
    status: str
    mime_type: str
    page_count: int | None
    parser_name: str
    parser_version: str
    normalized_text_sha256: str | None
    block_count: int
    chunk_count: int


class SourceUploadResponse(BaseModel):
    source_id: UUID
    status: str
    document: DocumentSummary


class SourceDetailResponse(BaseModel):
    source_id: UUID
    display_name: str
    original_filename: str
    status: str
    content_sha256: str
    current_document_id: UUID | None
    error_code: str | None
    error_detail: str | None
    document: DocumentSummary | None
    normalized_text: str | None
    blocks: list[dict]


def _document_summary(document: Document, chunk_count: int) -> DocumentSummary:
    return DocumentSummary(
        document_id=document.id,
        version=document.version,
        status=document.status,
        mime_type=document.mime_type,
        page_count=document.page_count,
        parser_name=document.parser_name,
        parser_version=document.parser_version,
        normalized_text_sha256=document.normalized_text_sha256,
        block_count=len(document.document_metadata.get("blocks", [])),
        chunk_count=chunk_count,
    )


@router.post("/uploads", response_model=SourceUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_source(
    file: UploadFile = File(...),
    display_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SourceUploadResponse:
    filename = Path(file.filename or "upload").name
    try:
        mime_type_for_path(Path(filename))
    except UnsupportedDocumentType as exc:
        raise NexusError(
            "UNSUPPORTED_MEDIA_TYPE", "Only PDF, DOC and DOCX files are supported.", 415
        ) from exc

    content = file.file.read(settings.max_upload_bytes + 1)
    if not content:
        raise NexusError("EMPTY_FILE", "The uploaded file is empty.")
    if len(content) > settings.max_upload_bytes:
        raise NexusError(
            "FILE_TOO_LARGE", f"The upload exceeds the {settings.max_upload_bytes} byte limit.", 413
        )

    artifact = store_artifact(settings.artifact_store_path, filename, content)
    source = db.scalar(select(Source).where(Source.content_sha256 == artifact.content_sha256))
    if source is not None and source.status != "failed":
        raise NexusError(
            "SOURCE_ALREADY_EXISTS", "A source with the same file content already exists.", 409
        )
    if source is None:
        source = Source(
            display_name=(display_name or filename).strip()[:200] or filename[:200],
            original_filename=filename[:255],
            kind="upload",
            status="processing",
            content_sha256=artifact.content_sha256,
        )
        db.add(source)
    else:
        source.display_name = (display_name or filename).strip()[:200] or filename[:200]
        source.original_filename = filename[:255]
        source.status = "processing"
        source.error_code = None
        source.error_detail = None
    db.commit()

    source.artifact_name = artifact.path.name
    document = ingest_source(db, source, artifact.path, settings)
    return SourceUploadResponse(
        source_id=source.id,
        status=source.status,
        document=_document_summary(document, document.document_metadata["chunk_count"]),
    )


@router.get("")
def list_sources(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    counts = (
        select(DocumentChunk.document_id, func.count().label("chunk_count"))
        .group_by(DocumentChunk.document_id)
        .subquery()
    )
    rows = db.execute(
        select(Source, func.coalesce(counts.c.chunk_count, 0))
        .outerjoin(counts, Source.current_document_id == counts.c.document_id)
        .order_by(Source.created_at.desc(), Source.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "sources": [
            {
                "source_id": source.id,
                "display_name": source.display_name,
                "original_filename": source.original_filename,
                "status": source.status,
                "current_document_id": source.current_document_id,
                "chunk_count": count,
                "error_code": source.error_code,
            }
            for source, count in rows
        ],
        "limit": limit,
        "offset": offset,
        "total": db.scalar(select(func.count()).select_from(Source)),
    }


@router.get("/{source_id}", response_model=SourceDetailResponse)
def get_source(source_id: UUID, db: Session = Depends(get_db)) -> SourceDetailResponse:
    source = db.get(Source, source_id)
    if source is None:
        raise NexusError("SOURCE_NOT_FOUND", "The requested source does not exist.", 404)
    document = db.get(Document, source.current_document_id) if source.current_document_id else None
    count = (
        db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
        )
        if document
        else 0
    )
    return SourceDetailResponse(
        source_id=source.id,
        display_name=source.display_name,
        original_filename=source.original_filename,
        status=source.status,
        content_sha256=source.content_sha256,
        current_document_id=source.current_document_id,
        error_code=source.error_code,
        error_detail=source.error_detail,
        document=_document_summary(document, count) if document else None,
        normalized_text=document.normalized_text if document else None,
        blocks=document.document_metadata.get("blocks", []) if document else [],
    )


@router.get("/{source_id}/chunks")
def get_source_chunks(
    source_id: UUID,
    document_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    source = db.get(Source, source_id)
    if source is None:
        raise NexusError("SOURCE_NOT_FOUND", "The requested source does not exist.", 404)
    selected_id = document_id or source.current_document_id
    if selected_id is None:
        raise NexusError("SOURCE_NOT_READY", "This source has no parsed document.", 409)
    document = db.get(Document, selected_id)
    if document is None or document.source_id != source.id:
        raise NexusError("DOCUMENT_NOT_FOUND", "The document does not belong to this source.", 404)
    chunks = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.sequence)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "source_id": source.id,
        "document_id": document.id,
        "document_version": document.version,
        "chunks": [
            {
                "chunk_id": chunk.id,
                "sequence": chunk.sequence,
                "text": chunk.text,
                "text_sha256": chunk.text_sha256,
                "char_count": len(chunk.text),
                "locator": chunk.locator,
            }
            for chunk in chunks
        ],
        "limit": limit,
        "offset": offset,
        "total": db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
        ),
    }
