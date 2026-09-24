from hashlib import sha256

from app.ingestion.artifacts import store_artifact


def test_original_filename_cannot_escape_artifact_directory(tmp_path):
    content = b"document fixture"
    artifact = store_artifact(tmp_path, "../../outside.pdf", content)
    assert artifact.path == tmp_path / f"{sha256(content).hexdigest()}.pdf"
    assert artifact.path.read_bytes() == content
    assert store_artifact(tmp_path, "renamed.pdf", content) == artifact
