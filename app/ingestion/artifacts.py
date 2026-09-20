from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from app.ingestion.docling_parser import mime_type_for_path


@dataclass(frozen=True)
class StoredArtifact:
    path: Path
    content_sha256: str
    byte_size: int


def store_artifact(root: Path, filename: str, content: bytes) -> StoredArtifact:
    """Store one supported upload under a deterministic content-addressed name."""

    suffix = Path(filename).suffix.lower()
    mime_type_for_path(Path(filename))

    content_sha256 = sha256(content).hexdigest()
    path = root / f"{content_sha256}{suffix}"
    root.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        path.write_bytes(content)

    return StoredArtifact(
        path=path,
        content_sha256=content_sha256,
        byte_size=len(content),
    )
