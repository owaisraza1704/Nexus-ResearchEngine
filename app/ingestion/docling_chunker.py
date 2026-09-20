from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from docling.chunking import HierarchicalChunker

from app.ingestion.docling_parser import ParsedDocument


class DocumentChunkingError(Exception):
    """Raised when Docling cannot produce chunks for a parsed document."""


@dataclass(frozen=True)
class ChunkDraft:
    sequence: int
    text: str
    locator: dict[str, Any]

    @property
    def text_sha256(self) -> str:
        return sha256(self.text.encode("utf-8")).hexdigest()


def chunk_document(document: ParsedDocument) -> tuple[ChunkDraft, ...]:
    """Adapt Docling's structure-aware chunks to the application boundary."""

    if document.native_document is None:
        raise DocumentChunkingError(
            "ParsedDocument does not contain a native Docling document"
        )

    try:
        chunker = HierarchicalChunker()
        chunks = tuple(
            ChunkDraft(
                sequence=sequence,
                text=chunk.text,
                locator=chunk.meta.export_json_dict(),
            )
            for sequence, chunk in enumerate(chunker.chunk(document.native_document))
        )
    except Exception as exc:
        raise DocumentChunkingError("Docling could not chunk the document") from exc

    if not chunks:
        raise DocumentChunkingError("Docling produced no chunks for the document")

    return chunks
