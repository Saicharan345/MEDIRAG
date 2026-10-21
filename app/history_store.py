import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models import (
    ChatSessionDetail,
    ChatSessionSummary,
    HistoryMessage,
    SavedLabReportRecord,
    SavedPrescriptionRecord,
)
from config import config


class HistoryStore:
    def __init__(self):
        self.path = config.STORAGE_PATH
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write({"chat_sessions": [], "prescriptions": [], "lab_reports": []})

    def create_or_get_session(self, session_id: Optional[str], question: str, language: str) -> dict:
        with self._lock:
            data = self._read()
            sessions = data["chat_sessions"]
            if session_id:
                for session in sessions:
                    if session["id"] == session_id:
                        session["updated_at"] = self._timestamp()
                        self._write(data)
                        return session

            created_at = self._timestamp()
            session = {
                "id": str(uuid.uuid4()),
                "title": self._make_title(question),
                "created_at": created_at,
                "updated_at": created_at,
                "language": language or config.DEFAULT_LANGUAGE,
                "messages": [],
            }
            sessions.insert(0, session)
            self._write(data)
            return session

    def append_chat_message(self, session_id: str, message: HistoryMessage) -> dict:
        with self._lock:
            data = self._read()
            for session in data["chat_sessions"]:
                if session["id"] == session_id:
                    session["messages"].append(message.model_dump())
                    session["updated_at"] = self._timestamp()
                    if len(session["messages"]) == 1 and message.role == "user":
                        session["title"] = self._make_title(message.content)
                    self._sort_sessions(data["chat_sessions"])
                    self._write(data)
                    return session
        raise KeyError(f"Chat session not found: {session_id}")

    def list_chat_sessions(self) -> List[ChatSessionSummary]:
        data = self._read()
        sessions = []
        for session in data["chat_sessions"]:
            sessions.append(
                ChatSessionSummary(
                    id=session["id"],
                    title=session["title"],
                    created_at=session["created_at"],
                    updated_at=session["updated_at"],
                    language=session.get("language", config.DEFAULT_LANGUAGE),
                    message_count=len(session.get("messages", [])),
                )
            )
        return sessions

    def get_chat_session(self, session_id: str) -> ChatSessionDetail:
        data = self._read()
        for session in data["chat_sessions"]:
            if session["id"] == session_id:
                return ChatSessionDetail(
                    id=session["id"],
                    title=session["title"],
                    created_at=session["created_at"],
                    updated_at=session["updated_at"],
                    language=session.get("language", config.DEFAULT_LANGUAGE),
                    message_count=len(session.get("messages", [])),
                    messages=[HistoryMessage(**message) for message in session.get("messages", [])],
                )
        raise KeyError(f"Chat session not found: {session_id}")

    def delete_chat_session(self, session_id: str) -> None:
        with self._lock:
            data = self._read()
            sessions = data["chat_sessions"]
            original_count = len(sessions)
            data["chat_sessions"] = [session for session in sessions if session["id"] != session_id]
            if len(data["chat_sessions"]) == original_count:
                raise KeyError(f"Chat session not found: {session_id}")
            self._write(data)

    def save_prescription(self, record: SavedPrescriptionRecord) -> SavedPrescriptionRecord:
        with self._lock:
            data = self._read()
            data["prescriptions"].insert(0, record.model_dump())
            self._write(data)
        return record

    def list_prescriptions(self) -> List[SavedPrescriptionRecord]:
        data = self._read()
        return [SavedPrescriptionRecord(**record) for record in data["prescriptions"]]

    def get_prescription(self, record_id: str) -> SavedPrescriptionRecord:
        data = self._read()
        for record in data["prescriptions"]:
            if record["id"] == record_id:
                return SavedPrescriptionRecord(**record)
        raise KeyError(f"Prescription record not found: {record_id}")

    def delete_prescription(self, record_id: str) -> None:
        with self._lock:
            data = self._read()
            records = data["prescriptions"]
            original_count = len(records)
            data["prescriptions"] = [record for record in records if record["id"] != record_id]
            if len(data["prescriptions"]) == original_count:
                raise KeyError(f"Prescription record not found: {record_id}")
            self._write(data)

    def save_lab_report(self, record: SavedLabReportRecord) -> SavedLabReportRecord:
        with self._lock:
            data = self._read()
            data["lab_reports"].insert(0, record.model_dump())
            self._write(data)
        return record

    def list_lab_reports(self) -> List[SavedLabReportRecord]:
        data = self._read()
        return [SavedLabReportRecord(**record) for record in data["lab_reports"]]

    def get_lab_report(self, record_id: str) -> SavedLabReportRecord:
        data = self._read()
        for record in data["lab_reports"]:
            if record["id"] == record_id:
                return SavedLabReportRecord(**record)
        raise KeyError(f"Lab report record not found: {record_id}")

    def delete_lab_report(self, record_id: str) -> None:
        with self._lock:
            data = self._read()
            records = data["lab_reports"]
            original_count = len(records)
            data["lab_reports"] = [record for record in records if record["id"] != record_id]
            if len(data["lab_reports"]) == original_count:
                raise KeyError(f"Lab report record not found: {record_id}")
            self._write(data)

    def _make_title(self, text: str) -> str:
        cleaned = " ".join((text or "").strip().split())
        if not cleaned:
            return "Untitled Session"
        return cleaned[:60] + ("..." if len(cleaned) > 60 else "")

    def _sort_sessions(self, sessions: List[dict]):
        sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read(self) -> Dict[str, Any]:
        default_payload = {"chat_sessions": [], "prescriptions": [], "lab_reports": []}
        if not os.path.exists(self.path):
            self._write(default_payload)
            return default_payload
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                if not isinstance(data, dict):
                    data = default_payload
                data.setdefault("chat_sessions", [])
                data.setdefault("prescriptions", [])
                data.setdefault("lab_reports", [])
                return data
        except Exception:
            self._write(default_payload)
            return default_payload

    def _write(self, payload: Dict[str, Any]):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)


history_store = HistoryStore()
