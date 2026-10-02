from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document

from . import smartart


def validate_docx(docx_path: str | Path) -> tuple[list[str], list[str]]:
    """Validate structural invariants required by this project's spec.

    Checks: the file is a valid DOCX openable by python-docx, at least one
    real Word "Heading 1" style is used (required for collapse/expand to
    work), no image parts exist (concept maps must never be pictures), and
    any SmartArt parts present pass smartart.validate_smartart_docx.
    """
    errors: list[str] = []
    warnings: list[str] = []
    docx_path = Path(docx_path)

    try:
        doc = Document(str(docx_path))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"python-docx could not reopen the file: {exc}")
        return errors, warnings

    heading_paragraphs = [
        p for p in doc.paragraphs if p.style is not None and p.style.name.startswith("Heading")
    ]
    heading_styles_used = {p.style.name for p in heading_paragraphs}

    if "Heading 1" not in heading_styles_used:
        errors.append("No paragraph uses the real 'Heading 1' Word style; collapse/expand will not work.")
    elif heading_paragraphs[0].style.name != "Heading 1":
        errors.append(
            "The first heading-styled paragraph is not 'Heading 1'; the lesson title must be Heading 1 "
            "and appear first so the whole document nests under it in Word's outline."
        )

    h1_count = sum(1 for name in (p.style.name for p in heading_paragraphs) if name == "Heading 1")
    if h1_count > 1:
        warnings.append(
            f"{h1_count} paragraphs use 'Heading 1'; expected exactly one (the lesson title) so the "
            "entire document collapses under a single top-level node."
        )

    try:
        with zipfile.ZipFile(docx_path) as zf:
            names = zf.namelist()
            media_parts = [n for n in names if n.startswith("word/media/")]
            if media_parts:
                errors.append(
                    f"Found {len(media_parts)} image part(s) under word/media/ - concept maps must be "
                    "real SmartArt, never images."
                )

            diagram_parts = [n for n in names if n.startswith("word/diagrams/")]
            if diagram_parts:
                sa_errors, sa_warnings = smartart.validate_smartart_docx(docx_path)
                errors.extend(sa_errors)
                warnings.extend(sa_warnings)
    except zipfile.BadZipFile:
        errors.append("Corrupt DOCX file (invalid ZIP).")

    return errors, warnings
