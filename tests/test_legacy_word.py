import subprocess
from types import SimpleNamespace

import pytest

from app.ingestion import legacy_word
from app.ingestion.docling_parser import DocumentParseError, parse_document
from app.ingestion.legacy_word import LegacyWordConversionError, convert_legacy_word


@pytest.fixture
def binary_doc(tmp_path):
    path = tmp_path / "legacy.doc"
    path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1fixture")
    return path


def test_rejects_text_renamed_to_doc(tmp_path):
    path = tmp_path / "text.doc"
    path.write_text("Not a binary Word file")
    with pytest.raises(DocumentParseError, match="Word 97"):
        parse_document(path)


def test_missing_office_is_actionable(binary_doc, tmp_path, monkeypatch):
    monkeypatch.setattr(legacy_word.shutil, "which", lambda _: None)
    with pytest.raises(LegacyWordConversionError, match="requires LibreOffice"):
        convert_legacy_word(binary_doc, tmp_path, 5)


@pytest.mark.parametrize("failure", ["timeout", "exit", "missing_output"])
def test_conversion_failures_are_explicit(binary_doc, tmp_path, monkeypatch, failure):
    monkeypatch.setattr(legacy_word.shutil, "which", lambda _: "/usr/bin/soffice")

    def run(command, **kwargs):
        if command[-1] == "--version":
            return SimpleNamespace(stdout="LibreOffice test")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if failure == "exit":
            raise subprocess.CalledProcessError(1, command)
        return SimpleNamespace()

    monkeypatch.setattr(legacy_word.subprocess, "run", run)
    with pytest.raises(LegacyWordConversionError):
        convert_legacy_word(binary_doc, tmp_path, 5)


def test_conversion_has_isolated_profile_and_preserves_original(binary_doc, tmp_path, monkeypatch):
    monkeypatch.setattr(legacy_word.shutil, "which", lambda _: "/usr/bin/soffice")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert 0 < kwargs["timeout"] <= 5
        if command[-1] == "--version":
            return SimpleNamespace(stdout="LibreOffice 25.2\n")
        assert f"-env:UserInstallation={(tmp_path / 'profile').as_uri()}" in command
        (tmp_path / "legacy.docx").write_bytes(b"converted")
        return SimpleNamespace()

    monkeypatch.setattr(legacy_word.subprocess, "run", run)
    converted, version = convert_legacy_word(binary_doc, tmp_path, 5)
    assert converted.read_bytes() == b"converted"
    assert binary_doc.read_bytes().endswith(b"fixture")
    assert version == "LibreOffice 25.2"
    assert len(calls) == 2
