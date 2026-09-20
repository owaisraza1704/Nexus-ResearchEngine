from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Document, DocumentChunk, Source
from app.db.session import get_db
from app.ingestion.artifacts import store_artifact
from app.ingestion.docling_chunker import DocumentChunkingError, chunk_document
from app.ingestion.docling_parser import (
    DocumentHasNoText,
    DocumentParseError,
    UnsupportedDocumentType,
    mime_type_for_path,
    parse_document,
)

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


def _error_response(
    code: str,
    message: str,
    *,
    status_code: int,
    retryable: bool = False,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
            }
        },
    )


def _document_summary(document: Document) -> DocumentSummary:
    blocks = document.document_metadata.get("blocks", [])
    return DocumentSummary(
        document_id=document.id,
        version=document.version,
        status=document.status,
        mime_type=document.mime_type,
        page_count=document.page_count,
        parser_name=document.parser_name,
        parser_version=document.parser_version,
        normalized_text_sha256=document.normalized_text_sha256,
        block_count=len(blocks),
    )


def _mark_source_failed(
    db: Session,
    source: Source,
    error_code: str,
    error_detail: str,
) -> None:
    source.status = "failed"
    source.error_code = error_code
    source.error_detail = error_detail
    db.commit()


@router.post(
    "/uploads",
    response_model=SourceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_source(
    file: UploadFile = File(...),
    display_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SourceUploadResponse | JSONResponse:
    filename = Path(file.filename or "upload").name

    try:
        mime_type_for_path(Path(filename))
    except UnsupportedDocumentType:
        return _error_response(
            "UNSUPPORTED_MEDIA_TYPE",
            "Only PDF and DOCX files are supported in the MVP.",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    content = file.file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        return _error_response(
            "FILE_TOO_LARGE",
            f"The upload exceeds the {settings.max_upload_bytes} byte limit.",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    artifact = store_artifact(settings.artifact_store_path, filename, content)
    duplicate = db.scalar(select(Source).where(Source.content_sha256 == artifact.content_sha256))
    if duplicate is not None:
        return _error_response(
            "SOURCE_ALREADY_EXISTS",
            "A source with the same file content already exists.",
            status_code=status.HTTP_409_CONFLICT,
        )

    source = Source(
        display_name=(display_name or filename).strip()[:200] or filename,
        original_filename=filename[:255],
        kind="upload",
        status="processing",
        content_sha256=artifact.content_sha256,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    try:
        parsed = parse_document(artifact.path)
        if parsed.page_count is not None and parsed.page_count > settings.max_document_pages:
            _mark_source_failed(
                db,
                source,
                "DOCUMENT_TOO_MANY_PAGES",
                f"The document exceeds the {settings.max_document_pages} page limit.",
            )
            return _error_response(
                "DOCUMENT_TOO_MANY_PAGES",
                f"The document exceeds the {settings.max_document_pages} page limit.",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        chunks = chunk_document(parsed)
    except DocumentHasNoText as exc:
        _mark_source_failed(db, source, "DOCUMENT_HAS_NO_TEXT", str(exc))
        return _error_response(
            "DOCUMENT_HAS_NO_TEXT",
            str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    except DocumentParseError as exc:
        _mark_source_failed(db, source, "DOCUMENT_PARSE_FAILED", str(exc))
        return _error_response(
            "DOCUMENT_PARSE_FAILED",
            str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    except DocumentChunkingError as exc:
        _mark_source_failed(db, source, "DOCUMENT_CHUNKING_FAILED", str(exc))
        return _error_response(
            "DOCUMENT_CHUNKING_FAILED",
            str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    document = Document(
        source_id=source.id,
        version=1,
        status="parsed",
        mime_type=mime_type_for_path(Path(filename)),
        parser_name=parsed.parser_name,
        parser_version=parsed.parser_version,
        normalized_text=parsed.normalized_text,
        normalized_text_sha256=parsed.normalized_text_sha256,
        page_count=parsed.page_count,
        document_metadata={
            "blocks": [
                {"text": block.text, "label": block.label, "locator": block.locator}
                for block in parsed.blocks
            ]
        },
        ready_at=None,
    )
    db.add(document)
    db.flush()
    for chunk in chunks:
        db.add(
            DocumentChunk(
                document_id=document.id,
                sequence=chunk.sequence,
                text=chunk.text,
                text_sha256=chunk.text_sha256,
                locator=chunk.locator,
            )
        )

    document.status = "ready"
    document.ready_at = datetime.now(timezone.utc)
    source.current_document_id = document.id
    source.status = "ready"
    db.commit()
    db.refresh(document)

    return SourceUploadResponse(
        source_id=source.id,
        status=source.status,
        document=_document_summary(document),
    )


@router.get("/{source_id}", response_model=SourceDetailResponse)
def get_source(source_id: UUID, db: Session = Depends(get_db)) -> SourceDetailResponse:
    source = db.get(Source, source_id)
    if source is None:
        return _error_response(
            "SOURCE_NOT_FOUND",
            "The requested source does not exist.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    document = db.get(Document, source.current_document_id) if source.current_document_id else None
    blocks = document.document_metadata.get("blocks", []) if document else []
    return SourceDetailResponse(
        source_id=source.id,
        display_name=source.display_name,
        original_filename=source.original_filename,
        status=source.status,
        content_sha256=source.content_sha256,
        current_document_id=source.current_document_id,
        error_code=source.error_code,
        error_detail=source.error_detail,
        document=_document_summary(document) if document else None,
        normalized_text=document.normalized_text if document else None,
        blocks=blocks,
    )
