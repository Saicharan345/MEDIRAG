from __future__ import annotations

from typing import List

import fitz

from config import config


class DocumentParser:
    def extract_pdf_text(self, pdf_bytes: bytes) -> str:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            parts: List[str] = []
            for page_index, page in enumerate(document):
                if page_index >= config.MAX_PDF_PAGES:
                    break
                text = page.get_text("text").strip()
                if text:
                    parts.append(f"Page {page_index + 1}:\n{text}")
            return "\n\n".join(parts).strip()

    def render_pdf_pages(self, pdf_bytes: bytes) -> List[bytes]:
        rendered_pages: List[bytes] = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            for page_index, page in enumerate(document):
                if page_index >= config.MAX_PDF_PAGES:
                    break
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                rendered_pages.append(pixmap.tobytes("png"))
        return rendered_pages


document_parser = DocumentParser()
