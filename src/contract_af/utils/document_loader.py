"""Load contracts from PDF, DOCX, or plain text files."""

from __future__ import annotations

from pathlib import Path

import pdfplumber
from docx import Document

_SUPPORTED_SUFFIXES = frozenset({".pdf", ".docx", ".doc", ".txt", ".md", ".text"})


def load_document(file_path: str | Path) -> tuple[str, list[str]]:
    """Load a document and return ``(full_text, per_page_texts)``.

    Supported formats: ``.pdf``, ``.docx`` / ``.doc``, ``.txt`` / ``.md``.

    Raises
    ------
    FileNotFoundError
        If *file_path* does not exist.
    ValueError
        If the file extension is not supported.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported file type: {suffix}. "
            f"Supported: {', '.join(sorted(_SUPPORTED_SUFFIXES))}"
        )

    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix in (".docx", ".doc"):
        return _load_docx(path)
    return _load_text(path)


def _load_pdf(path: Path) -> tuple[str, list[str]]:
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return "\n\n".join(pages), pages


def _load_docx(path: Path) -> tuple[str, list[str]]:
    doc = Document(str(path))
    full_text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    # DOCX has no natural page boundaries — return as single page
    return full_text, [full_text]


def _load_text(path: Path) -> tuple[str, list[str]]:
    text = path.read_text(encoding="utf-8")
    return text, [text]
