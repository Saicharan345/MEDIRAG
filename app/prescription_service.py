import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from config import config
from app.drug_lookup import drug_lookup_service
from app.history_store import history_store
from app.llm_providers import get_provider
from app.models import PrescriptionAnalysisResponse, PrescriptionMedicine, SavedPrescriptionRecord


class PrescriptionService:
    def __init__(self):
        self.provider = get_provider()

    def analyze(self, image_bytes: bytes, mime_type: str, file_name: str = "prescription-image", language: str = "English") -> PrescriptionAnalysisResponse:
        print(f"[PRESCRIPTION] File received: {file_name}")
        print(f"[PRESCRIPTION] Content type: {mime_type}")
        print(f"[PRESCRIPTION] File size: {len(image_bytes)} bytes")
        print(f"[PRESCRIPTION] Configured vision model: {getattr(config, 'GROQ_VISION_MODEL', 'unknown')}")

        if not self.provider.supports_vision():
            raise ValueError("The configured provider does not support image analysis.")

        prompt = """
You are reading a prescription image for educational software.
Extract only what you can see with reasonable confidence.
Return valid JSON with this exact shape:
{
  "prescription_summary": "short string",
  "extracted_text": "short raw transcription if readable",
  "handwriting_quality": "clear|mixed|poor",
  "warnings": ["..."],
  "medicines": [
    {
      "name": "medicine name",
      "strength": "if visible",
      "dosage_instructions": "if visible",
      "confidence": 0.0,
      "notes": "uncertainty or context"
    }
  ]
}
Rules:
- Do not invent medicines.
- If handwriting is unclear, keep the item but lower confidence and explain uncertainty.
- If no medicine can be read, return an empty medicines array.
- Keep the response concise and complete valid JSON under 400 words.
"""

        result = self.provider.analyze_image(image_bytes=image_bytes, mime_type=mime_type, prompt=prompt)
        if not isinstance(result, dict):
            raise ValueError("Invalid response from vision provider.")

        if result.get("error"):
            print(f"[PRESCRIPTION ERROR] Provider error: {result['error']}")
            raise ValueError(result["error"])

        medicines: List[PrescriptionMedicine] = []
        raw_warnings = result.get("warnings", [])
        warnings = list(raw_warnings) if isinstance(raw_warnings, list) else [str(raw_warnings)] if raw_warnings else []

        handwriting_quality = str(result.get("handwriting_quality", "mixed")).lower()
        if handwriting_quality == "poor":
            warnings.append("The handwriting or image quality looked poor, so medicine names may be inaccurate.")

        raw_medicines = result.get("medicines", [])
        if not isinstance(raw_medicines, list):
            raw_medicines = []

        for item in raw_medicines:
            if isinstance(item, str):
                raw_name = item.strip()
                item_dict = {"name": raw_name, "strength": None, "dosage_instructions": None, "confidence": 0.5, "notes": None}
            elif isinstance(item, dict):
                raw_name = (item.get("name") or "").strip()
                item_dict = item
            else:
                continue

            if not raw_name:
                continue

            enrichment = drug_lookup_service.lookup(raw_name)
            try:
                confidence = float(item_dict.get("confidence") or 0.0)
            except (ValueError, TypeError):
                confidence = 0.5

            if enrichment.get("source") == "No verified match":
                warnings.append(f"I could not verify a strong reference match for {raw_name}.")

            medicines.append(
                PrescriptionMedicine(
                    name=raw_name,
                    normalized_name=enrichment.get("normalized_name"),
                    strength=item_dict.get("strength"),
                    dosage_instructions=item_dict.get("dosage_instructions"),
                    common_use=enrichment.get("common_use"),
                    explanation=enrichment.get("explanation"),
                    confidence=round(min(max(confidence, 0.0), 1.0), 2),
                    source=enrichment.get("source") or "Local drug reference",
                    notes=item_dict.get("notes"),
                    rxnorm_rxcui=enrichment.get("rxnorm_rxcui"),
                )
            )

        if not medicines:
            warnings.append("No medicines could be extracted confidently from this image.")

        print(f"[PRESCRIPTION] Extracted medicines count: {len(medicines)}")

        summary = result.get("prescription_summary") or "Prescription image analyzed for likely medicines and common uses."
        response = PrescriptionAnalysisResponse(
            summary=summary,
            extracted_text=result.get("extracted_text"),
            medicines=medicines,
            warnings=self._dedupe(warnings),
            language=language,
        )

        if language.lower() != "english":
            response = self._translate_response(response, language)

        record = SavedPrescriptionRecord(
            id=str(uuid.uuid4()),
            title=self._make_title(medicines, file_name),
            created_at=self._timestamp(),
            file_name=file_name,
            language=response.language,
            summary=response.summary,
            extracted_text=response.extracted_text,
            medicines=response.medicines,
            warnings=response.warnings,
        )
        history_store.save_prescription(record)
        response.record_id = record.id
        response.title = record.title
        print(f"[PRESCRIPTION] Successfully saved record: {record.id}")
        return response

    def _translate_response(self, response: PrescriptionAnalysisResponse, language: str) -> PrescriptionAnalysisResponse:
        response.summary = self.provider.translate_text(response.summary, language)
        if response.extracted_text:
            response.extracted_text = self.provider.translate_text(response.extracted_text, language)
        response.warnings = [self.provider.translate_text(item, language) for item in response.warnings]
        translated_medicines = []
        for medicine in response.medicines:
            translated_medicines.append(
                medicine.model_copy(
                    update={
                        "common_use": self.provider.translate_text(medicine.common_use or "", language) if medicine.common_use else None,
                        "explanation": self.provider.translate_text(medicine.explanation or "", language) if medicine.explanation else None,
                        "notes": self.provider.translate_text(medicine.notes or "", language) if medicine.notes else None,
                        "dosage_instructions": self.provider.translate_text(medicine.dosage_instructions or "", language) if medicine.dosage_instructions else None,
                    }
                )
            )
        response.medicines = translated_medicines
        response.language = language
        response.disclaimer = self.provider.translate_text(response.disclaimer, language)
        return response

    def _make_title(self, medicines: List[PrescriptionMedicine], file_name: str) -> str:
        if medicines:
            names = [medicine.normalized_name or medicine.name for medicine in medicines[:2]]
            suffix = "..." if len(medicines) > 2 else ""
            return f"Prescription: {', '.join(names)}{suffix}"
        return f"Prescription: {file_name}"

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


prescription_service = PrescriptionService()
