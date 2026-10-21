import re
import uuid
from datetime import datetime, timezone
from typing import List

from app.document_parser import document_parser
from app.history_store import history_store
from app.llm_providers import get_provider
from app.models import LabReportResponse, SavedLabReportRecord
from app.vector_store import vector_store
from config import config


class LabReportService:
    def __init__(self):
        self.provider = get_provider()

    def interpret(
        self,
        report_text: str,
        language: str = "English",
        file_name: str | None = None,
        extra_warnings: List[str] | None = None,
    ) -> LabReportResponse:
        cleaned = (report_text or "").strip()
        if not cleaned:
            raise ValueError("Please paste a lab report or lab values to interpret.")

        print("[LAB REPORT] Starting RAG interpretation")
        search_query = self._normalize_search_query(cleaned, language)
        search_results = vector_store.query(search_query, n_results=config.TOP_K, domain_filter="Lab Medicine")
        contexts = search_results.get("documents", [[]])[0]
        metadatas = search_results.get("metadatas", [[]])[0]
        context_blocks = []
        for index, context in enumerate(contexts[: config.MAX_CONTEXTS]):
            title = metadatas[index].get("title", "Lab reference")
            context_blocks.append(f"Reference {index + 1} ({title}):\n{context}")
        context_str = "\n\n".join(context_blocks) if context_blocks else "No grounded lab-reference context was found."

        prompt = f"""
You are helping interpret a lab report for educational use.
Use only the values and wording explicitly present in the report text below together with the provided lab-reference context.
Do not invent diagnoses, reference ranges, missing values, or management plans.
If reference ranges are not provided, say that clearly.
Respond in {language}.

Report text:
{cleaned}

Lab reference context:
{context_str}

Instructions:
- Keep the interpretation structured, clear, and concise (about 350-500 words).
- Under Important Findings, prioritize flagged and abnormal values with their specific test names, results, units, and reference ranges, and summarize normal panels briefly.
- Include sections: Summary, Important Findings, Limitations, Safety Notes.

Return valid JSON with this shape:
{{
  "summary": "short summary",
  "interpretation": "markdown text with sections Summary, Important Findings, Limitations, Safety Notes",
  "warnings": ["..."],
  "detected_markers": ["..."]
}}
"""

        result = self.provider.generate_json(
            prompt,
            system_prompt=(
                "You are a careful medical educator. Stay within the provided report text and avoid unsupported claims."
            ),
        )
        if result.get("error"):
            raise ValueError(result["error"])

        warnings = result.get("warnings", [])
        markers = result.get("detected_markers", [])
        if not markers:
            markers = self._detect_markers(cleaned)
        if not contexts:
            warnings.append("No grounded lab-reference match was found in the local dataset, so the interpretation may be more limited.")

        response = LabReportResponse(
            summary=result.get("summary") or "Lab report interpreted from the provided text.",
            interpretation=result.get("interpretation") or "I could not produce a structured interpretation.",
            warnings=self._dedupe([*(extra_warnings or []), *warnings]),
            detected_markers=markers,
            extracted_text=cleaned,
            file_name=file_name,
            language=language,
        )

        return self._save_response(response, markers, file_name, language)

    def interpret_file(self, file_bytes: bytes, content_type: str, file_name: str, language: str = "English") -> LabReportResponse:
        file_size = len(file_bytes) if file_bytes else 0
        print(f"[LAB REPORT] File received: {file_name}")
        print(f"[LAB REPORT] Content type: {content_type}")
        print(f"[LAB REPORT] File size: {file_size} bytes")

        if not file_bytes or file_size == 0:
            raise ValueError("The uploaded file is empty. Please upload a valid lab report file.")

        content_type_lower = (content_type or "").lower()
        file_name_lower = (file_name or "").lower()
        warnings: List[str] = []

        is_pdf = content_type_lower == "application/pdf" or file_name_lower.endswith(".pdf") or file_bytes.startswith(b"%PDF")
        is_image = any(img_type in content_type_lower for img_type in ["image/png", "image/jpeg", "image/jpg", "image/webp"]) or any(file_name_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"])

        if is_pdf:
            try:
                page_count = document_parser.get_page_count(file_bytes)
                print(f"[LAB REPORT] PDF pages: {page_count}")
                if page_count == 0:
                    raise ValueError("The uploaded PDF has no pages.")
            except Exception as exc:
                raise ValueError(f"Corrupted or invalid PDF file: {exc}") from exc

            extracted_text, _ = document_parser.extract_pdf_text_with_meta(file_bytes)
            print(f"[LAB REPORT] Extracted text length: {len(extracted_text)}")

            # Check if extracted text is usable (> 60 characters with alphanumeric content)
            has_usable_text = len(extracted_text.strip()) >= 60 and bool(re.search(r"[a-zA-Z0-9]{3,}", extracted_text))

            if has_usable_text:
                print("[LAB REPORT] Using direct PDF text extraction")
            else:
                print("[LAB REPORT] No usable PDF text found; using OCR")
                try:
                    page_images = document_parser.render_pdf_pages(file_bytes)
                    ocr_parts = []
                    for page_index, page_img in enumerate(page_images):
                        ocr_text = self._extract_text_from_image(page_img, "image/png", page_number=page_index + 1)
                        if ocr_text:
                            ocr_parts.append(f"Page {page_index + 1}:\n{ocr_text}")
                    if ocr_parts:
                        extracted_text = "\n\n".join(ocr_parts)
                        warnings.append("This PDF looked image-based, so OCR was used instead of embedded PDF text.")
                    print(f"[LAB REPORT] OCR text length: {len(extracted_text)}")
                except Exception as exc:
                    raise ValueError(f"OCR processing failed on PDF pages: {exc}") from exc

            if len(extracted_text.strip()) < 20:
                raise ValueError("No readable text could be extracted from this PDF. Try a clearer PDF or paste the report text directly.")

        elif is_image:
            img_mime = content_type_lower if "image/" in content_type_lower else "image/png"
            if "jpeg" in img_mime or "jpg" in img_mime:
                img_mime = "image/jpeg"
            elif "webp" in img_mime:
                img_mime = "image/webp"
            else:
                img_mime = "image/png"

            print("[LAB REPORT] Using image OCR")
            try:
                extracted_text = self._extract_text_from_image(file_bytes, img_mime)
                print(f"[LAB REPORT] OCR text length: {len(extracted_text)}")
            except Exception as exc:
                raise ValueError(f"Image OCR processing failed: {exc}") from exc

            if len(extracted_text.strip()) < 15:
                raise ValueError("Could not read enough text from the uploaded lab report image.")
        else:
            raise ValueError("Unsupported file type. Please upload a PNG, JPG, WEBP, or PDF lab report.")

        return self.interpret(extracted_text, language=language, file_name=file_name, extra_warnings=warnings)

    def _extract_text_from_image(self, image_bytes: bytes, mime_type: str, page_number: int | None = None) -> str:
        prompt = (
            "Read this lab report image and extract the visible report text as accurately as possible. "
            "Preserve test names, values, units, reference ranges, and page structure. "
            "Do not summarize. Return valid JSON with the key extracted_text."
        )
        if page_number is not None:
            prompt += f" This is page {page_number} of a PDF-derived lab report."

        result = self.provider.analyze_image(image_bytes=image_bytes, mime_type=mime_type, prompt=prompt)
        if result.get("error"):
            raise ValueError(result["error"])
        extracted_text = result.get("extracted_text")
        if isinstance(extracted_text, str) and extracted_text.strip():
            return extracted_text.strip()
        if isinstance(extracted_text, list) and extracted_text:
            return "\n".join(str(item) for item in extracted_text)
        raise ValueError("Could not read enough text from the uploaded lab report image.")

    def _save_response(
        self,
        response: LabReportResponse,
        markers: List[str],
        file_name: str | None,
        language: str,
    ) -> LabReportResponse:
        record = SavedLabReportRecord(
            id=str(uuid.uuid4()),
            title=self._make_title(markers),
            created_at=self._timestamp(),
            file_name=file_name,
            language=language,
            summary=response.summary,
            interpretation=response.interpretation,
            extracted_text=response.extracted_text,
            warnings=response.warnings,
            detected_markers=response.detected_markers,
        )
        history_store.save_lab_report(record)
        response.record_id = record.id
        response.title = record.title
        return response

    def _detect_markers(self, text: str) -> List[str]:
        candidates = [
            "hemoglobin", "wbc", "rbc", "platelet", "platelets", "hematocrit", "pcv", "mcv", "mch", "mchc", "rdw",
            "creatinine", "urea", "bun", "egfr",
            "bilirubin", "alt", "ast", "alp", "alkaline phosphatase", "total protein", "albumin",
            "sodium", "potassium", "chloride",
            "fasting glucose", "glucose", "hba1c", "tsh", "free t4", "free t3",
            "vitamin d", "vitamin b12", "crp", "esr",
            "hdl", "ldl", "triglycerides", "cholesterol", "uric acid",
            "urinalysis", "urine", "hematuria",
        ]
        lower = text.lower()
        found = []
        for item in candidates:
            if item in lower:
                formatted = item.upper() if len(item) <= 4 else item.title()
                if formatted not in found:
                    found.append(formatted)
        return found[:15]

    def _make_title(self, markers: List[str]) -> str:
        if markers:
            return f"Lab report: {', '.join(markers[:3])}"
        return "Lab report interpretation"

    def _normalize_search_query(self, report_text: str, language: str) -> str:
        if language.lower() != "english":
            try:
                result = self.provider.generate_json(
                    f"""Normalize this lab report text into a concise English retrieval query.
Preserve marker names, units, and numeric values.
Return JSON with the key "english_query".

Lab report text:
{report_text[:1500]}
""",
                    system_prompt="You convert multilingual medical text into a concise English retrieval query without adding facts.",
                )
                if not result.get("error"):
                    english_query = result.get("english_query")
                    if isinstance(english_query, str) and english_query.strip():
                        return english_query.strip()
            except Exception:
                pass

        # For English or fallback, build focused search query with detected markers and core lab terms
        markers = self._detect_markers(report_text)
        if markers:
            return f"Lab report reference evaluation: {' '.join(markers)}"
        return report_text[:500]

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _dedupe(self, items: List[str]) -> List[str]:
        seen = set()
        output = []
        for item in items:
            cleaned = item.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            output.append(cleaned)
        return output


lab_report_service = LabReportService()
