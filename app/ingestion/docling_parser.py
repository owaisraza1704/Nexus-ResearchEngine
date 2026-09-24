from dataclasses import dataclass, field
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

SUPPORTED_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class DocumentParseError(Exception):
    """Raised when Docling cannot parse a supported document."""


class DocumentHasNoText(DocumentParseError):
    """Raised when a document contains no extractable text."""


class UnsupportedDocumentType(DocumentParseError):
    """Raised when the file extension is outside the Stage 0 contract."""


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    label: str
    locator: dict[str, Any]


@dataclass(frozen=True)
class ParsedDocument:
    normalized_text: str
    blocks: tuple[ParsedBlock, ...]
    page_count: int | None
    parser_name: str
    parser_version: str
    # Kept in memory so native Docling features can reuse the same conversion.
    native_document: Any | None = field(default=None, repr=False, compare=False)

    @property
    def normalized_text_sha256(self) -> str:
        return sha256(self.normalized_text.encode("utf-8")).hexdigest()


def mime_type_for_path(path: Path) -> str:
    mime_type = SUPPORTED_MIME_TYPES.get(path.suffix.lower())
    if mime_type is None:
        raise UnsupportedDocumentType(f"Unsupported document type: {path.suffix or '<none>'}")
    return mime_type


def parse_document(
    path: Path, *, max_pages: int = 100, timeout_seconds: float = 180.0
) -> ParsedDocument:
    """Parse one supported document and preserve its source provenance."""

    mime_type_for_path(path)

    try:
        from docling.datamodel.base_models import ConversionStatus

        conversion = _document_converter(timeout_seconds).convert(path, max_num_pages=max_pages)
        if conversion.status != ConversionStatus.SUCCESS:
            raise DocumentParseError("Docling did not finish the entire document")
        document = conversion.document
    except Exception as exc:
        raise DocumentParseError(
            f"Docling could not fully parse {path.name}. "
            f"Use a valid text PDF (at most {max_pages} pages) or DOCX within the parse time limit."
        ) from exc

    blocks: list[ParsedBlock] = []
    normalized_parts: list[str] = []
    normalized_offset = 0

    for item in document.texts:
        text = _normalize_text(getattr(item, "text", ""))
        if not text:
            continue

        if normalized_parts:
            normalized_parts.append("\n\n")
            normalized_offset += 2

        start = normalized_offset
        normalized_parts.append(text)
        normalized_offset += len(text)

        blocks.append(
            ParsedBlock(
                text=text,
                label=str(getattr(item, "label", "text")),
                locator=_build_locator(item, start=start, end=normalized_offset),
            )
        )

    if not blocks:
        raise DocumentHasNoText("The document contains no extractable text")

    pages = getattr(document, "pages", None)
    page_count = len(pages) if pages else None

    return ParsedDocument(
        normalized_text="".join(normalized_parts),
        blocks=tuple(blocks),
        page_count=page_count,
        parser_name="docling",
        parser_version=_docling_version(),
        native_document=document,
    )


def _normalize_text(value: str) -> str:
    lines = [line.rstrip() for line in value.strip().splitlines()]
    return "\n".join(lines).strip()


def _build_locator(item: Any, *, start: int, end: int) -> dict[str, Any]:
    locator: dict[str, Any] = {
        "char_start": start,
        "char_end": end,
        "label": str(getattr(item, "label", "text")),
    }

    provenance = getattr(item, "prov", None)
    if not provenance:
        return locator

    source = provenance[0]
    locator["page"] = source.page_no
    if source.charspan:
        locator["source_char_start"] = source.charspan[0]
        locator["source_char_end"] = source.charspan[1]

    bbox = getattr(source, "bbox", None)
    if bbox is not None:
        origin = getattr(bbox.coord_origin, "value", str(bbox.coord_origin))
        locator["bbox"] = {
            "left": bbox.l,
            "top": bbox.t,
            "right": bbox.r,
            "bottom": bbox.b,
            "coord_origin": origin,
        }

    return locator


def _docling_version() -> str:
    try:
        return version("docling")
    except PackageNotFoundError:
        return "unknown"


def _document_converter(timeout_seconds: float) -> Any:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=PdfPipelineOptions(
                    do_ocr=False,
                    do_table_structure=False,
                    document_timeout=timeout_seconds,
                )
            )
        }
    )
