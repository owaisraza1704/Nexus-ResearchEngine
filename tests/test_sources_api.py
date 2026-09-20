import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api import sources as sources_api
from app.config import Settings
from app.db.models import ChunkEmbedding, Document, DocumentChunk, Source
from app.embeddings.azure_openai import EmbeddingResult
from app.ingestion.docling_chunker import ChunkDraft
from app.ingestion.docling_parser import DocumentHasNoText, ParsedBlock, ParsedDocument
from app.main import app


class InMemorySession:
    def __init__(self) -> None:
        self.sources: dict[uuid.UUID, Source] = {}
        self.documents: dict[uuid.UUID, Document] = {}
        self.chunks: dict[uuid.UUID, DocumentChunk] = {}
        self.embeddings: dict[uuid.UUID, ChunkEmbedding] = {}

    def scalar(self, statement: Any) -> None:
        del statement
        return None

    def add(self, value: Source | Document | DocumentChunk | ChunkEmbedding) -> None:
        if value.id is None:
            value.id = uuid.uuid4()
        if isinstance(value, Source):
            self.sources[value.id] = value
        elif isinstance(value, Document):
            self.documents[value.id] = value
        elif isinstance(value, DocumentChunk):
            self.chunks[value.id] = value
        else:
            self.embeddings[value.id] = value

    def commit(self) -> None:
        return None

    def flush(self) -> None:
        return None

    def refresh(self, value: Source | Document) -> None:
        del value

    def get(
        self,
        model: type[Source] | type[Document],
        object_id: uuid.UUID,
    ) -> Source | Document | None:
        if model is Source:
            return self.sources.get(object_id)
        return self.documents.get(object_id)

    def close(self) -> None:
        return None


def test_upload_source_persists_and_exposes_parsed_blocks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db = InMemorySession()
    settings = Settings(artifact_store_path=tmp_path)
    parsed = ParsedDocument(
        normalized_text="Heading\n\nBody",
        blocks=(
            ParsedBlock(
                text="Heading",
                label="section_header",
                locator={"page": 1, "char_start": 0, "char_end": 7},
            ),
            ParsedBlock(
                text="Body",
                label="text",
                locator={"page": 1, "char_start": 9, "char_end": 13},
            ),
        ),
        page_count=1,
        parser_name="docling",
        parser_version="test",
    )

    def fake_parse_document(path: Path) -> ParsedDocument:
        assert path.read_bytes() == b"document"
        return parsed

    chunks = (
        ChunkDraft(
            sequence=0,
            text="Heading",
            locator={"headings": ["Research"], "doc_items": []},
        ),
        ChunkDraft(
            sequence=1,
            text="Body",
            locator={"headings": ["Research"], "doc_items": []},
        ),
    )

    def fake_chunk_document(value: ParsedDocument) -> tuple[ChunkDraft, ...]:
        assert value is parsed
        return chunks

    embeddings = (
        EmbeddingResult(
            vector=(0.1, 0.2, 0.3),
            model="embedding-large",
            deployment="embedding-large",
            prompt_tokens=None,
        ),
        EmbeddingResult(
            vector=(0.4, 0.5, 0.6),
            model="embedding-large",
            deployment="embedding-large",
            prompt_tokens=None,
        ),
    )

    def fake_embed_texts(
        values: list[str],
        value_settings: Settings,
    ) -> tuple[EmbeddingResult, ...]:
        assert values == ["Heading", "Body"]
        assert value_settings is settings
        return embeddings

    monkeypatch.setattr(sources_api, "parse_document", fake_parse_document)
    monkeypatch.setattr(sources_api, "chunk_document", fake_chunk_document)
    monkeypatch.setattr(sources_api, "embed_texts", fake_embed_texts)
    app.dependency_overrides[sources_api.get_db] = lambda: db
    app.dependency_overrides[sources_api.get_settings] = lambda: settings

    try:
        client = TestClient(app)
        response = client.post(
            "/v1/sources/uploads",
            files={"file": ("research.pdf", b"document", "application/pdf")},
            data={"display_name": "Research source"},
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["status"] == "ready"
        assert payload["document"]["status"] == "ready"
        assert payload["document"]["block_count"] == 2
        assert len(db.chunks) == 2
        stored_chunks = sorted(db.chunks.values(), key=lambda chunk: chunk.sequence)
        assert [chunk.text for chunk in stored_chunks] == ["Heading", "Body"]
        assert stored_chunks[0].locator["headings"] == ["Research"]
        assert len(db.embeddings) == 2
        stored_embeddings = sorted(
            db.embeddings.values(),
            key=lambda embedding: embedding.chunk_id,
        )
        assert all(embedding.provider == "azure_openai" for embedding in stored_embeddings)
        assert all(embedding.dimensions == 3 for embedding in stored_embeddings)

        source_id = payload["source_id"]
        detail = client.get(f"/v1/sources/{source_id}")

        assert detail.status_code == 200
        assert detail.json()["normalized_text"] == "Heading\n\nBody"
        assert detail.json()["blocks"][0]["locator"]["page"] == 1
        assert db.documents[next(iter(db.documents))].ready_at is not None
    finally:
        app.dependency_overrides.clear()


def test_upload_source_records_a_chunking_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db = InMemorySession()
    settings = Settings(artifact_store_path=tmp_path)
    parsed = ParsedDocument(
        normalized_text="Body",
        blocks=(
            ParsedBlock(
                text="Body",
                label="text",
                locator={"char_start": 0, "char_end": 4},
            ),
        ),
        page_count=1,
        parser_name="docling",
        parser_version="test",
    )

    monkeypatch.setattr(sources_api, "parse_document", lambda path: parsed)

    def fail_chunking(value: ParsedDocument) -> tuple[ChunkDraft, ...]:
        del value
        raise sources_api.DocumentChunkingError("chunking failed")

    monkeypatch.setattr(sources_api, "chunk_document", fail_chunking)
    app.dependency_overrides[sources_api.get_db] = lambda: db
    app.dependency_overrides[sources_api.get_settings] = lambda: settings

    try:
        response = TestClient(app).post(
            "/v1/sources/uploads",
            files={"file": ("research.pdf", b"document", "application/pdf")},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "DOCUMENT_CHUNKING_FAILED"
        assert len(db.documents) == 0
        source = next(iter(db.sources.values()))
        assert source.status == "failed"
        assert source.error_code == "DOCUMENT_CHUNKING_FAILED"
    finally:
        app.dependency_overrides.clear()


def test_upload_source_records_an_embedding_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db = InMemorySession()
    settings = Settings(artifact_store_path=tmp_path)
    parsed = ParsedDocument(
        normalized_text="Body",
        blocks=(
            ParsedBlock(
                text="Body",
                label="text",
                locator={"char_start": 0, "char_end": 4},
            ),
        ),
        page_count=1,
        parser_name="docling",
        parser_version="test",
    )
    chunk = ChunkDraft(sequence=0, text="Body", locator={"doc_items": []})

    monkeypatch.setattr(sources_api, "parse_document", lambda path: parsed)
    monkeypatch.setattr(sources_api, "chunk_document", lambda value: (chunk,))

    def fail_embedding(values: list[str], value_settings: Settings) -> tuple[EmbeddingResult, ...]:
        del values, value_settings
        raise sources_api.AzureEmbeddingError("embedding failed")

    monkeypatch.setattr(sources_api, "embed_texts", fail_embedding)
    app.dependency_overrides[sources_api.get_db] = lambda: db
    app.dependency_overrides[sources_api.get_settings] = lambda: settings

    try:
        response = TestClient(app).post(
            "/v1/sources/uploads",
            files={"file": ("research.pdf", b"document", "application/pdf")},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "DOCUMENT_EMBEDDING_FAILED"
        assert len(db.documents) == 0
        source = next(iter(db.sources.values()))
        assert source.status == "failed"
        assert source.error_code == "DOCUMENT_EMBEDDING_FAILED"
    finally:
        app.dependency_overrides.clear()


def test_upload_source_records_a_parse_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db = InMemorySession()
    settings = Settings(artifact_store_path=tmp_path)

    def fake_parse_document(path: Path) -> ParsedDocument:
        del path
        raise DocumentHasNoText("The document contains no extractable text")

    monkeypatch.setattr(sources_api, "parse_document", fake_parse_document)
    app.dependency_overrides[sources_api.get_db] = lambda: db
    app.dependency_overrides[sources_api.get_settings] = lambda: settings

    try:
        response = TestClient(app).post(
            "/v1/sources/uploads",
            files={"file": ("scan.pdf", b"document", "application/pdf")},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "DOCUMENT_HAS_NO_TEXT"
        assert len(db.sources) == 1
        source = next(iter(db.sources.values()))
        assert source.status == "failed"
        assert source.error_code == "DOCUMENT_HAS_NO_TEXT"
    finally:
        app.dependency_overrides.clear()
