from typing import List, Optional

from pydantic import BaseModel, Field


class GuidelineEntry(BaseModel):
    id: str
    domain: str
    title: str
    source: str
    category: str
    content: str
    key_recommendations: List[str]
    last_updated: str
    aliases: List[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    question: str
    domain: Optional[str] = None
    language: str = "English"
    session_id: Optional[str] = None


class Citation(BaseModel):
    source: str
    title: str
    category: str
    domain: str
    content: str
    last_updated: Optional[str] = None
    score: Optional[float] = None


class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]
    confidence: float
    message: Optional[str] = None
    guardrail_status: Optional[str] = None
    language: str = "English"
    search_query: Optional[str] = None
    session_id: Optional[str] = None
    session_title: Optional[str] = None
    disclaimer: str = "DISCLAIMER: This information is for educational and training purposes only. It is not a substitute for professional medical judgment, diagnosis, or treatment. Always consult with a qualified healthcare provider."


class SearchResult(BaseModel):
    content: str
    metadata: dict
    score: float


class IngestResponse(BaseModel):
    status: str
    count: int
    message: str


class PrescriptionMedicine(BaseModel):
    name: str
    normalized_name: Optional[str] = None
    strength: Optional[str] = None
    dosage_instructions: Optional[str] = None
    common_use: Optional[str] = None
    explanation: Optional[str] = None
    confidence: float = 0.0
    source: str = "Local drug reference"
    notes: Optional[str] = None
    rxnorm_rxcui: Optional[str] = None


class PrescriptionAnalysisResponse(BaseModel):
    summary: str
    extracted_text: Optional[str] = None
    medicines: List[PrescriptionMedicine]
    warnings: List[str] = Field(default_factory=list)
    language: str = "English"
    record_id: Optional[str] = None
    title: Optional[str] = None
    disclaimer: str = "DISCLAIMER: Prescription image analysis can misread handwriting or low-quality images. Always verify the medicine name and instructions with a licensed clinician or pharmacist before using this information."


class LabReportRequest(BaseModel):
    report_text: str
    language: str = "English"


class LabReportResponse(BaseModel):
    summary: str
    interpretation: str
    warnings: List[str] = Field(default_factory=list)
    detected_markers: List[str] = Field(default_factory=list)
    extracted_text: Optional[str] = None
    file_name: Optional[str] = None
    language: str = "English"
    record_id: Optional[str] = None
    title: Optional[str] = None
    disclaimer: str = "DISCLAIMER: Lab report interpretation here is educational only. It may miss context such as units, reference ranges, symptoms, medications, and clinical history. Confirm any result with a qualified clinician."


class HistoryMessage(BaseModel):
    role: str
    content: str
    timestamp: str
    citations: List[Citation] = Field(default_factory=list)
    confidence: Optional[float] = None
    guardrail_status: Optional[str] = None
    disclaimer: Optional[str] = None
    domain: Optional[str] = None
    language: Optional[str] = None


class ChatSessionSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    language: str = "English"
    message_count: int = 0


class ChatSessionDetail(ChatSessionSummary):
    messages: List[HistoryMessage] = Field(default_factory=list)


class SavedPrescriptionRecord(BaseModel):
    id: str
    title: str
    created_at: str
    file_name: str
    language: str = "English"
    summary: str
    extracted_text: Optional[str] = None
    medicines: List[PrescriptionMedicine] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SavedLabReportRecord(BaseModel):
    id: str
    title: str
    created_at: str
    file_name: Optional[str] = None
    language: str = "English"
    summary: str
    interpretation: str
    extracted_text: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    detected_markers: List[str] = Field(default_factory=list)
