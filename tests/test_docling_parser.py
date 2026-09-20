from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ingestion import docling_parser
from app.ingestion.docling_parser import (
    DocumentHasNoText,
    DocumentParseError,
    UnsupportedDocumentType,
    mime_type_for_path,
    parse_document,
)


def _provenance(page: int, start: int, end: int) -> SimpleNamespace:
    return SimpleNamespace(
        page_no=page,
        charspan=(start, end),
        bbox=SimpleNamespace(
            l=1.0,
            t=2.0,
            r=3.0,
            b=4.0,
            coord_origin=SimpleNamespace(value="BOTTOMLEFT"),
        ),
    )


class FakeConverter:
    def __init__(
        self,
        document: SimpleNamespace | None = None,
        error: Exception | None = None,
    ) -> None:
        self.document = document
        self.error = error

    def convert(self, path: Path) -> SimpleNamespace:
        del path
        if self.error:
            raise self.error
        return SimpleNamespace(document=self.document)


def test_parse_document_normalizes_text_and_preserves_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = SimpleNamespace(
        texts=[
            SimpleNamespace(
                text=" Heading  \n",
                label="section_header",
                prov=[_provenance(1, 0, 8)],
            ),
            SimpleNamespace(
                text="Body text\nwith a line break",
                label="text",
                prov=[_provenance(1, 9, 36)],
            ),
        ],
        pages={1: object()},
    )
    monkeypatch.setattr(
        docling_parser,
        "_document_converter",
        lambda: FakeConverter(document=document),
    )

    parsed = parse_document(Path("sample.pdf"))

    assert parsed.normalized_text == "Heading\n\nBody text\nwith a line break"
    assert parsed.page_count == 1
    assert parsed.parser_name == "docling"
    assert len(parsed.blocks) == 2
    assert parsed.blocks[0].locator["page"] == 1
    assert parsed.blocks[0].locator["char_start"] == 0
    assert parsed.blocks[1].locator["char_start"] == len("Heading\n\n")
    assert len(parsed.normalized_text_sha256) == 64


def test_mime_type_for_path_supports_pdf_and_docx() -> None:
    assert mime_type_for_path(Path("document.pdf")) == "application/pdf"
    assert mime_type_for_path(Path("document.docx")) == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_parse_document_rejects_unsupported_type() -> None:
    with pytest.raises(UnsupportedDocumentType):
        parse_document(Path("document.txt"))


def test_parse_document_rejects_no_text(monkeypatch: pytest.MonkeyPatch) -> None:
    document = SimpleNamespace(texts=[], pages={1: object()})
    monkeypatch.setattr(
        docling_parser,
        "_document_converter",
        lambda: FakeConverter(document=document),
    )

    with pytest.raises(DocumentHasNoText):
        parse_document(Path("scan.pdf"))


def test_parse_document_wraps_parser_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        docling_parser,
        "_document_converter",
        lambda: FakeConverter(error=ValueError("malformed")),
    )

    with pytest.raises(DocumentParseError, match="Docling could not parse"):
        parse_document(Path("broken.pdf"))
