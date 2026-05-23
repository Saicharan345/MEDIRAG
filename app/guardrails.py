import math
import re
from typing import List, Tuple


class Guardrails:
    INJECTION_PATTERNS = [
        r"ignore (previous|all|the) instructions",
        r"system prompt",
        r"developer message",
        r"act as",
        r"you are now",
        r"bypass",
        r"jailbreak",
    ]

    EMERGENCY_KEYWORDS = [
        "suicide", "kill myself", "end my life", "self harm", "self-harm",
        "heart attack right now", "chest pain with sweating", "cannot breathe",
        "can't breathe", "trouble breathing", "heavy bleeding", "unconscious",
        "seizure right now", "stroke symptoms", "overdose", "severe allergic reaction",
    ]

    PERSONAL_REQUEST_PATTERNS = [
        r"\bi have\b", r"\bmy child\b", r"\bmy mother\b", r"\bmy father\b",
        r"\bfor me\b", r"\bfor my\b", r"\bwhat should i take\b",
    ]

    MEDICAL_KEYWORDS = {
        "a1c", "antibiotic", "asthma", "blood", "bp", "breathing", "cbc", "cholesterol",
        "copd", "creatinine", "cough", "diabetes", "diagnosis", "dose", "dosage", "drug",
        "ecg", "ekg", "fever", "glucose", "hba1c", "hdl", "hemoglobin", "hypertension",
        "infection", "insulin", "lab", "labs", "ldl", "medicine", "medication", "mg",
        "ml", "otitis", "pain", "pediatric", "pharmacology", "platelet", "prescription",
        "protocol", "rbc", "respiratory", "screening", "serum", "symptom", "symptoms",
        "tablet", "test", "treatment", "triglycerides", "wbc",
    }

    MEDICAL_PATTERNS = [
        r"\b(?:dr\.?|doctor|nurse|clinic|hospital|patient)\b",
        r"\b(?:xray|x-ray|mri|ct|ultrasound)\b",
        r"\b(?:tsh|t3|t4|a1c|hba1c|cmp|cbc|bun)\b",
        r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|kg|ml|mmhg|mmol\/l|mg\/dl)\b",
        r"\b(?:take|takes|taking|prescribed|prescribe)\b.*\b(?:mg|tablet|capsule|medicine|drug)\b",
    ]

    def validate_input(self, question: str) -> Tuple[bool, str]:
        if not question or not question.strip():
            return False, "Please enter a medical or medication-related question."

        normalized = question.lower().strip()
        if any(re.search(pattern, normalized) for pattern in self.INJECTION_PATTERNS):
            return False, "This request looks like a prompt-injection attempt, so I can't use it."

        return True, "ok"

    def check_emergency(self, question: str) -> bool:
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in self.EMERGENCY_KEYWORDS)

    def is_personal_request(self, question: str) -> bool:
        question_lower = question.lower()
        return any(re.search(pattern, question_lower) for pattern in self.PERSONAL_REQUEST_PATTERNS)

    def looks_medical_question(self, question: str) -> bool:
        normalized = question.lower().strip()
        if not normalized:
            return False

        tokens = set(re.findall(r"[a-z0-9\-/]+", normalized))
        if tokens & self.MEDICAL_KEYWORDS:
            return True

        return any(re.search(pattern, normalized) for pattern in self.MEDICAL_PATTERNS)

    def retrieval_supported(self, scores: List[float], min_score: float) -> bool:
        if not scores:
            return False
        return max(scores) >= min_score

    def query_matches_context(self, question: str, contexts: List[str]) -> bool:
        query_terms = self._important_terms(question)
        if not query_terms:
            return False

        context_terms = self._important_terms(" ".join(contexts))
        return bool(query_terms & context_terms)

    def calculate_confidence(self, scores: List[float], answer: str, context: str) -> float:
        if not scores or not context.strip():
            return 0.0

        top_score = max(scores)
        score_component = min(0.55, math.log1p(max(top_score, 0.0)) / 4)
        overlap_component = 0.0

        answer_terms = self._important_terms(answer)
        context_terms = self._important_terms(context)
        if answer_terms:
            overlap = len(answer_terms & context_terms) / max(len(answer_terms), 1)
            overlap_component = min(0.3, overlap * 0.35)

        confidence = 0.25 + score_component + overlap_component
        return round(min(0.97, max(0.0, confidence)), 2)

    def build_guardrail_note(self, question: str) -> str:
        if self.is_personal_request(question):
            return "Educational guidance only. Do not treat this as personalized medical advice."
        return "Grounded in retrieved sources only."

    def validate_image(self, content_type: str, size_bytes: int, max_size_bytes: int) -> Tuple[bool, str]:
        allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
        if content_type not in allowed_types:
            return False, "Please upload a PNG, JPG, or WEBP image."

        if size_bytes <= 0:
            return False, "The uploaded file was empty."

        if size_bytes > max_size_bytes:
            return False, f"Please upload an image smaller than {max_size_bytes // (1024 * 1024)} MB."

        return True, "ok"

    def _important_terms(self, text: str) -> set[str]:
        stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "have", "into",
            "will", "your", "about", "only", "used", "using", "than", "most",
            "more", "when", "what", "where", "which", "their",
        }
        tokens = re.findall(r"[a-z0-9\-]{3,}", text.lower())
        return {token for token in tokens if token not in stopwords}


guardrails = Guardrails()
