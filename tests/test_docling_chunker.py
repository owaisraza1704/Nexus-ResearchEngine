from pathlib import Path

import pytest

from app.ingestion.docling_chunker import chunk_document
from app.ingestion.docling_parser import parse_document

ARCHITECTURE_PDF = (
    Path(__file__).parents[1] / "architecture" / "Agentic_RAG_Research_Platform_Synopsis.pdf"
)


@pytest.mark.skipif(
    not ARCHITECTURE_PDF.exists(), reason="Optional local architecture fixture absent"
)
def test_chunk_document_uses_docling_hierarchical_chunker() -> None:
    parsed = parse_document(ARCHITECTURE_PDF)

    chunks = chunk_document(parsed)

    assert len(chunks) > 1
    assert [chunk.sequence for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0].text == "PROJECT SYNOPSIS"
    assert all(chunk.text.strip() for chunk in chunks)
    assert all("doc_items" in chunk.locator for chunk in chunks)
    assert any("Project Objective" in (chunk.locator.get("headings") or []) for chunk in chunks)
    assert all(len(chunk.text_sha256) == 64 for chunk in chunks)
