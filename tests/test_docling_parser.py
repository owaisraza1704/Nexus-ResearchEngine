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

    def convert(self, path: Path, **kwargs) -> SimpleNamespace:
        del path
        if self.error:
            raise self.error
        return SimpleNamespace(document=self.document, status="success")


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
        lambda timeout: FakeConverter(document=document),
    )

    parsed = parse_document(Path("sample.pdf"))

    assert parsed.normalized_text == "Heading\n\nBody text\nwith a line break"
    assert parsed.page_count == 1
    assert parsed.parser_name == "docling"
    assert len(parsed.blocks) == 2
    assert parsed.native_document is document
    assert parsed.blocks[0].locator["page"] == 1
    assert parsed.blocks[0].locator["char_start"] == 0
    assert parsed.blocks[1].locator["char_start"] == len("Heading\n\n")
    assert len(parsed.normalized_text_sha256) == 64


def test_mime_type_for_path_supports_pdf_and_docx() -> None:
    assert mime_type_for_path(Path("document.pdf")) == "application/pdf"
    assert mime_type_for_path(Path("document.doc")) == "application/msword"
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
        lambda timeout: FakeConverter(document=document),
    )

    with pytest.raises(DocumentHasNoText):
        parse_document(Path("scan.pdf"))


def test_parse_document_wraps_parser_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        docling_parser,
        "_document_converter",
        lambda timeout: FakeConverter(error=ValueError("malformed")),
    )

    with pytest.raises(DocumentParseError, match="Docling could not fully parse"):
        parse_document(Path("broken.pdf"))


def test_doc_conversion_preserves_parser_and_conversion_metadata(monkeypatch, tmp_path):
    original = tmp_path / "original.doc"
    original.write_bytes(b"original bytes")
    document = SimpleNamespace(
        texts=[SimpleNamespace(text="Legacy source evidence", label="text", prov=[])], pages={}
    )

    def convert(path, directory, timeout):
        assert path == original
        assert timeout > 0
        output = directory / "original.docx"
        output.write_bytes(b"converted bytes")
        return output, "LibreOffice test"

    monkeypatch.setattr(docling_parser, "convert_legacy_word", convert)
    monkeypatch.setattr(docling_parser, "_document_converter", lambda _: FakeConverter(document))
    parsed = parse_document(original)
    assert parsed.normalized_text == "Legacy source evidence"
    assert parsed.parser_name == "docling"
    assert parsed.conversion_metadata["converter_version"] == "LibreOffice test"
    assert parsed.conversion_metadata["locator_basis"] == "converted_docx_blocks"
    assert original.read_bytes() == b"original bytes"
