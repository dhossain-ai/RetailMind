from pathlib import Path
from typing import Iterator

import fitz  # PyMuPDF


def extract_pages(pdf_path: str | Path) -> Iterator[tuple[int, str]]:
    """Yield (page_number, text) for each page in the PDF.

    Page numbers are 1-based to match human-readable citations.
    Pages with no extractable text are skipped.
    """
    doc = fitz.open(str(pdf_path))
    try:
        for i, page in enumerate(doc, start=1):
            text = page.get_text()
            if text.strip():
                yield i, text
    finally:
        doc.close()
