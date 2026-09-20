import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api import sources as sources_api
from app.config import Settings
from app.db.models import Document, Source
from app.ingestion.docling_parser import DocumentHasNoText, ParsedBlock, ParsedDocument
from app.main import app


class InMemorySession:
    def __init__(self) -> None:
        self.sources: dict[uuid.UUID, Source] = {}
        self.documents: dict[uuid.UUID, Document] = {}

    def scalar(self, statement: Any) -> None:
        del statement
        return None

    def add(self, value: Source | Document) -> None:
        if value.id is None:
            value.id = uuid.uuid4()
        if isinstance(value, Source):
            self.sources[value.id] = value
        else:
            self.documents[value.id] = value

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

    monkeypatch.setattr(sources_api, "parse_document", fake_parse_document)
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
        assert payload["status"] == "parsed"
        assert payload["document"]["status"] == "parsed"
        assert payload["document"]["block_count"] == 2

        source_id = payload["source_id"]
        detail = client.get(f"/v1/sources/{source_id}")

        assert detail.status_code == 200
        assert detail.json()["normalized_text"] == "Heading\n\nBody"
        assert detail.json()["blocks"][0]["locator"]["page"] == 1
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
