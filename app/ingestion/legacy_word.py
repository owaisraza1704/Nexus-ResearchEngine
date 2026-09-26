"""Convert Word 97–2003 uploads with LibreOffice; Docling still owns text extraction."""

import shutil
import subprocess
from pathlib import Path
from time import monotonic


class LegacyWordConversionError(ValueError):
    pass


def convert_legacy_word(path: Path, workdir: Path, timeout_seconds: float) -> tuple[Path, str]:
    # LibreOffice can import plain text renamed to .doc; require the binary Word container.
    with path.open("rb") as source:
        if source.read(8) != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise LegacyWordConversionError("Expected a Word 97–2003 binary DOC file.")
    executable = shutil.which("soffice") or shutil.which("libreoffice")
    if not executable:
        raise LegacyWordConversionError(
            "DOC conversion requires LibreOffice. Use the Docker setup."
        )
    started = monotonic()
    try:
        converter_version = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=min(5, timeout_seconds),
        ).stdout.strip()
        # A unique profile prevents two worker processes from sharing an office instance.
        subprocess.run(
            [
                executable,
                f"-env:UserInstallation={(workdir / 'profile').as_uri()}",
                "--headless",
                "--nologo",
                "--norestore",
                "--convert-to",
                "docx:Office Open XML Text",
                "--outdir",
                str(workdir),
                str(path.resolve()),
            ],
            capture_output=True,
            check=True,
            timeout=max(0.01, timeout_seconds - (monotonic() - started)),
        )
    except subprocess.TimeoutExpired as exc:
        raise LegacyWordConversionError(
            "DOC conversion exceeded the ingestion time limit."
        ) from exc
    except (subprocess.CalledProcessError, OSError) as exc:
        raise LegacyWordConversionError("LibreOffice could not convert this DOC document.") from exc
    converted = workdir / (path.stem + ".docx")
    if not converted.is_file() or not converted.stat().st_size:
        raise LegacyWordConversionError("LibreOffice produced no DOCX. Check the DOC document.")
    return converted, converter_version
