"""The UI's local research library: real workspaces, selected sources, and persisted drafts."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.sources import _document_summary, get_source, get_source_chunks
from app.config import Settings, get_settings
from app.db.job_models import ResearchJob, WorkspaceSource
from app.db.models import Document, DocumentChunk, Source, Workspace
from app.db.research_models import ResearchResult
from app.db.session import get_db
from app.errors import NexusError
from app.ingestion.artifacts import store_artifact
from app.ingestion.docling_parser import UnsupportedDocumentType, mime_type_for_path
from app.jobs.contracts import JobMode
from app.jobs.queue import enqueue

router = APIRouter(prefix="/v1/projects", tags=["local research workspaces"])


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(default="", max_length=4000)
    mode: JobMode = "agentic"
    top_k: int = Field(default=4, ge=1, le=20)
    retrieval_strategy: Literal["vector", "hybrid"] = "hybrid"
    source_ids: list[UUID] = Field(default_factory=list, max_length=10)
    web_urls: list[str] = Field(default_factory=list, max_length=5)


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=400)
    draft: Draft | None = None


def project_or_404(db: Session, project_id: UUID, *, lock: bool = False) -> Workspace:
    query = select(Workspace).where(Workspace.id == project_id)
    workspace = db.scalar(query.with_for_update() if lock else query)
    if workspace is None:
        raise NexusError("WORKSPACE_NOT_FOUND", "This research workspace does not exist.", 404)
    return workspace


def scoped_source(db: Session, project_id: UUID, source_id: UUID) -> Source:
    project_or_404(db, project_id)
    source = db.scalar(
        select(Source)
        .join(WorkspaceSource)
        .where(WorkspaceSource.workspace_id == project_id, Source.id == source_id)
    )
    if source is None:
        # Old results remain inspectable after source selection changes.
        raise NexusError("SOURCE_NOT_FOUND", "This source is not attached to this research.", 404)
    return source


def project_response(db: Session, project: Workspace) -> dict:
    rows = db.execute(
        select(Source, Document)
        .join(WorkspaceSource, WorkspaceSource.source_id == Source.id)
        .outerjoin(Document, Source.current_document_id == Document.id)
        .where(WorkspaceSource.workspace_id == project.id)
        .order_by(Source.created_at.desc(), Source.id)
    ).all()
    counts = (
        dict(
            db.execute(
                select(DocumentChunk.document_id, func.count())
                .where(DocumentChunk.document_id.in_([doc.id for _, doc in rows if doc]))
                .group_by(DocumentChunk.document_id)
            ).all()
        )
        if rows
        else {}
    )
    runs = db.execute(
        select(ResearchJob, ResearchResult.status)
        .outerjoin(ResearchResult, ResearchResult.research_run_id == ResearchJob.run_id)
        .where(ResearchJob.workspace_id == project.id)
        .order_by(ResearchJob.created_at.desc())
    ).all()
    return {
        "id": project.id,
        "title": project.name,
        "description": project.description,
        "updated_at": project.updated_at,
        "draft": {**Draft().model_dump(), **project.draft},
        "sources": [
            {
                "id": source.id,
                "name": source.display_name,
                "kind": source.kind,
                "type": "WEB"
                if source.kind == "web"
                else Path(source.original_filename).suffix[1:].upper(),
                "status": source.status,
                "pages": doc.page_count if doc else None,
                "chunks": counts.get(doc.id, 0) if doc else 0,
                "document_id": doc.id if doc else None,
                "version": doc.version if doc else None,
                "created_at": source.created_at,
                "error_code": source.error_code,
                "error_detail": source.error_detail,
                "attempts": source.ingestion_attempts,
            }
            for source, doc in rows
        ],
        "runs": [
            {
                "id": run.id,
                "question": run.question,
                "mode": run.mode,
                "status": run.status,
                "outcome": outcome,
                "created_at": run.created_at,
                "completed_at": run.completed_at,
            }
            for run, outcome in runs
        ],
    }


@router.get("")
def list_projects(
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    projects = db.scalars(
        select(Workspace).order_by(Workspace.updated_at.desc()).limit(limit).offset(offset)
    ).all()
    return {
        "projects": [project_response(db, project) for project in projects],
        "total": db.scalar(select(func.count()).select_from(Workspace)),
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=201)
def create_project(request: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    project = Workspace(
        name=request.title,
        description=request.description,
        slug=str(uuid4()),
        draft=Draft().model_dump(mode="json"),
        policy={},
    )
    db.add(project)
    db.commit()
    return project_response(db, project)


@router.get("/{project_id}")
def get_project(project_id: UUID, db: Session = Depends(get_db)) -> dict:
    return project_response(db, project_or_404(db, project_id))


@router.patch("/{project_id}")
def update_project(
    project_id: UUID,
    request: ProjectUpdate,
    db: Session = Depends(get_db),
) -> dict:
    project = project_or_404(db, project_id, lock=True)
    if request.title is not None:
        project.name = request.title
    if request.description is not None:
        project.description = request.description
    if request.draft is not None:
        allowed = set(
            db.scalars(
                select(WorkspaceSource.source_id).where(WorkspaceSource.workspace_id == project_id)
            )
        )
        if not set(request.draft.source_ids).issubset(allowed):
            raise NexusError(
                "SOURCE_ACCESS_DENIED", "The draft selects a source from another research.", 403
            )
        project.draft = request.draft.model_dump(mode="json")
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    return project_response(db, project)


@router.post("/{project_id}/sources/uploads", status_code=202)
def upload_project_source(
    project_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    project = project_or_404(db, project_id, lock=True)
    filename = Path(file.filename or "upload").name[:255]
    content = file.file.read(settings.max_upload_bytes + 1)
    if not content:
        raise NexusError("EMPTY_FILE", "The uploaded file is empty.")
    if len(content) > settings.max_upload_bytes:
        raise NexusError("FILE_TOO_LARGE", "The document exceeds the upload size limit.", 413)
    try:
        artifact = store_artifact(settings.artifact_store_path, filename, content)
    except UnsupportedDocumentType as exc:
        raise NexusError(
            "UNSUPPORTED_MEDIA_TYPE", "Upload a PDF, DOC or DOCX document.", 415
        ) from exc
    # A repeated upload attaches the existing content instead of making a second copy.
    db.execute(
        insert(Source)
        .values(
            id=uuid4(),
            display_name=filename[:200],
            original_filename=filename,
            content_sha256=artifact.content_sha256,
            kind="upload",
            status="registered",
            artifact_name=artifact.path.name,
        )
        .on_conflict_do_nothing(index_elements=["content_sha256"])
    )
    source = db.scalar(
        select(Source).where(Source.content_sha256 == artifact.content_sha256).with_for_update()
    )
    source.artifact_name = artifact.path.name
    db.execute(
        insert(WorkspaceSource)
        .values(workspace_id=project.id, source_id=source.id)
        .on_conflict_do_nothing()
    )
    if source.status not in {"ready", "processing"}:
        source.status = "processing"
        source.error_code = source.error_detail = None
        source.ingestion_attempts = 0
        source.ingestion_job_id = enqueue(
            db, "nexus.ingest", lock=f"source:{source.id}", source_id=str(source.id)
        )
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"source_id": source.id, "status": source.status}


@router.post("/{project_id}/sources/{source_id}")
def attach_source(project_id: UUID, source_id: UUID, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id, lock=True)
    if db.get(Source, source_id) is None:
        raise NexusError("SOURCE_NOT_FOUND", "This source does not exist.", 404)
    db.execute(
        insert(WorkspaceSource)
        .values(workspace_id=project.id, source_id=source_id)
        .on_conflict_do_nothing()
    )
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    return project_response(db, project)


@router.post("/{project_id}/sources/{source_id}/retry", status_code=202)
def retry_source(
    project_id: UUID,
    source_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    project_or_404(db, project_id, lock=True)
    source = scoped_source(db, project_id, source_id)
    if source.status != "failed" or source.kind != "upload":
        raise NexusError("SOURCE_NOT_RETRYABLE", "Only failed uploads can be retried.", 409)
    source.status = "processing"
    source.error_code = source.error_detail = None
    source.ingestion_attempts = 0
    source.ingestion_job_id = enqueue(
        db, "nexus.ingest", lock=f"source:{source.id}", source_id=str(source.id)
    )
    db.commit()
    return {"source_id": source.id, "status": source.status}


@router.get("/{project_id}/sources/{source_id}")
def inspect_source(
    project_id: UUID,
    source_id: UUID,
    document_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    scoped_source(db, project_id, source_id)
    response = get_source(source_id, db)
    if document_id is None or document_id == response.current_document_id:
        return response
    document = db.get(Document, document_id)
    if document is None or document.source_id != source_id:
        raise NexusError("DOCUMENT_NOT_FOUND", "The snapshot does not belong to this source.", 404)
    count = db.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
    )
    return response.model_copy(
        update={
            "document": _document_summary(document, count),
            "normalized_text": document.normalized_text,
            "blocks": document.document_metadata.get("blocks", []),
        }
    )


@router.get("/{project_id}/sources/{source_id}/chunks/{chunk_id}")
def inspect_chunk(
    project_id: UUID,
    source_id: UUID,
    chunk_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
):
    scoped_source(db, project_id, source_id)
    chunk = db.scalar(
        select(DocumentChunk)
        .join(Document)
        .where(
            DocumentChunk.id == chunk_id,
            DocumentChunk.document_id == document_id,
            Document.source_id == source_id,
        )
    )
    if chunk is None:
        raise NexusError("CHUNK_NOT_FOUND", "This passage is outside the selected snapshot.", 404)
    return {
        "chunk_id": chunk.id,
        "sequence": chunk.sequence,
        "text": chunk.text,
        "text_sha256": chunk.text_sha256,
        "char_count": len(chunk.text),
        "locator": chunk.locator,
    }


@router.get("/{project_id}/sources/{source_id}/chunks")
def inspect_chunks(
    project_id: UUID,
    source_id: UUID,
    document_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    scoped_source(db, project_id, source_id)
    return get_source_chunks(source_id, document_id, limit, offset, db)


@router.get("/{project_id}/sources/{source_id}/file")
def source_file(
    project_id: UUID,
    source_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    source = scoped_source(db, project_id, source_id)
    if source.kind == "web":
        document = db.get(Document, source.current_document_id)
        return PlainTextResponse(document.normalized_text if document else "")
    name = source.artifact_name or (
        source.content_sha256 + Path(source.original_filename).suffix.lower()
    )
    path = settings.artifact_store_path / Path(name).name
    if not path.is_file():
        raise NexusError("ARTIFACT_NOT_FOUND", "The original document is unavailable.", 404)
    return FileResponse(
        path,
        filename=source.original_filename,
        content_disposition_type="inline",
        media_type=mime_type_for_path(path),
    )
