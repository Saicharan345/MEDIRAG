import re
from typing import List, Tuple

import fitz

from config import config


class DocumentParser:
    def get_page_count(self, pdf_bytes: bytes) -> int:
        if not pdf_bytes:
            return 0
        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
                return len(document)
        except Exception as exc:
            raise ValueError(f"Corrupted or invalid PDF file: {exc}") from exc

    def extract_pdf_text_with_meta(self, pdf_bytes: bytes) -> Tuple[str, int]:
        if not pdf_bytes:
            raise ValueError("Uploaded PDF file is empty.")

        try:
            document = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise ValueError(f"Corrupted or invalid PDF file: {exc}") from exc

        parts: List[str] = []
        total_pages = len(document)

        try:
            for page_index in range(min(total_pages, config.MAX_PDF_PAGES)):
                page = document[page_index]
                text = page.get_text("text")
                cleaned_page_text = self._clean_extracted_text(text)
                if cleaned_page_text:
                    parts.append(f"Page {page_index + 1}:\n{cleaned_page_text}")
        finally:
            document.close()

        return "\n\n".join(parts).strip(), total_pages

    def extract_pdf_text(self, pdf_bytes: bytes) -> str:
        text, _ = self.extract_pdf_text_with_meta(pdf_bytes)
        return text

    def render_pdf_pages(self, pdf_bytes: bytes) -> List[bytes]:
        if not pdf_bytes:
            raise ValueError("Uploaded PDF file is empty.")

        try:
            document = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise ValueError(f"Corrupted or invalid PDF file: {exc}") from exc

        rendered_pages: List[bytes] = []
        try:
            for page_index in range(min(len(document), config.MAX_PDF_PAGES)):
                page = document[page_index]
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                rendered_pages.append(pixmap.tobytes("png"))
        finally:
            document.close()

        return rendered_pages

    def _clean_extracted_text(self, text: str) -> str:
        if not text:
            return ""
        # Remove null characters and non-printable control chars, keeping newline, tab, carriage return
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # Normalize excessive multiple blank lines (keep up to two newlines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


document_parser = DocumentParser()
