import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

from config import config


class DrugLookupService:
    def __init__(self):
        self.data_path = Path(config.BASE_DIR) / "data" / "drug_reference.json"
        self.entries = self._load_entries()

    def _load_entries(self) -> List[dict]:
        if not self.data_path.exists():
            return []

        with self.data_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload.get("guidelines", [])

    def lookup(self, raw_name: str) -> Dict[str, Optional[str]]:
        if not raw_name:
            return self._empty_result(raw_name)

        local_entry = self._match_local(raw_name)
        rxnorm_rxcui = self.lookup_rxnorm(raw_name)

        if local_entry:
            return {
                "name": raw_name,
                "normalized_name": local_entry["title"],
                "common_use": self._extract_common_use(local_entry["content"]),
                "explanation": local_entry["content"],
                "source": local_entry["source"],
                "rxnorm_rxcui": rxnorm_rxcui,
            }

        online_entry = self.lookup_openfda(raw_name)
        if online_entry:
            return {
                "name": raw_name,
                "normalized_name": raw_name.title(),
                "common_use": online_entry["common_use"],
                "explanation": online_entry["explanation"],
                "source": online_entry["source"],
                "rxnorm_rxcui": rxnorm_rxcui,
            }

        return self._empty_result(raw_name, rxnorm_rxcui=rxnorm_rxcui)

    def lookup_rxnorm(self, raw_name: str) -> Optional[str]:
        if not config.ENABLE_ONLINE_DRUG_LOOKUP:
            return None

        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(
                    f"{config.RXNAV_BASE_URL}/rxcui.json?name={quote(raw_name)}&search=2"
                )
                response.raise_for_status()
                data = response.json()
        except Exception:
            return None

        ids = data.get("idGroup", {}).get("rxnormId", [])
        return ids[0] if ids else None

    def lookup_openfda(self, raw_name: str) -> Optional[Dict[str, str]]:
        if not config.ENABLE_ONLINE_DRUG_LOOKUP:
            return None

        escaped_name = raw_name.replace('"', '\\"')
        queries = [
            f'openfda.generic_name:"{escaped_name}"',
            f'openfda.brand_name:"{escaped_name}"',
        ]

        with httpx.Client(timeout=8.0) as client:
            for query in queries:
                try:
                    response = client.get(config.OPENFDA_BASE_URL, params={"search": query, "limit": 1})
                    response.raise_for_status()
                    payload = response.json()
                except Exception:
                    continue

                results = payload.get("results", [])
                if not results:
                    continue

                record = results[0]
                common_use = self._first_text(record, ["indications_and_usage", "purpose", "description"])
                if not common_use:
                    continue

                short_text = self._summarize_text(common_use)
                return {
                    "common_use": short_text,
                    "explanation": short_text,
                    "source": "openFDA drug labeling",
                }

        return None

    def _match_local(self, raw_name: str) -> Optional[dict]:
        normalized = self._normalize_name(raw_name)
        if not normalized:
            return None

        best_match: Optional[Tuple[int, dict]] = None
        for entry in self.entries:
            candidates = [entry.get("title", "")]
            candidates.extend(entry.get("aliases", []))
            normalized_candidates = [self._normalize_name(candidate) for candidate in candidates if candidate]

            for candidate in normalized_candidates:
                if candidate == normalized:
                    return entry
                if candidate and (candidate in normalized or normalized in candidate):
                    score = abs(len(candidate) - len(normalized))
                    if best_match is None or score < best_match[0]:
                        best_match = (score, entry)

        return best_match[1] if best_match else None

    def _normalize_name(self, value: str) -> str:
        lowered = value.lower()
        lowered = re.sub(r"\b(tab(?:let)?|cap(?:sule)?|inj(?:ection)?|syrup|mg|mcg|ml)\b", " ", lowered)
        lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
        return " ".join(lowered.split()).strip()

    def _extract_common_use(self, content: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", content.strip())
        return sentences[0] if sentences else content.strip()

    def _first_text(self, record: dict, fields: List[str]) -> str:
        for field in fields:
            value = record.get(field)
            if isinstance(value, list) and value:
                return value[0]
            if isinstance(value, str) and value.strip():
                return value
        return ""

    def _summarize_text(self, text: str, max_length: int = 280) -> str:
        clean = re.sub(r"\s+", " ", text).strip()
        if len(clean) <= max_length:
            return clean
        truncated = clean[:max_length].rsplit(" ", 1)[0].strip()
        return f"{truncated}..."

    def _empty_result(self, raw_name: str, rxnorm_rxcui: Optional[str] = None) -> Dict[str, Optional[str]]:
        return {
            "name": raw_name,
            "normalized_name": raw_name.title() if raw_name else None,
            "common_use": "No grounded drug-reference match was found in the local starter set.",
            "explanation": "I could not reliably explain this medicine from the current local drug-reference set. Please verify the name manually or ask a pharmacist.",
            "source": "No verified match",
            "rxnorm_rxcui": rxnorm_rxcui,
        }


drug_lookup_service = DrugLookupService()
