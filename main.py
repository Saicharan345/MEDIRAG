import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.guardrails import guardrails
from app.history_store import history_store
from app.ingest import ingest_guidelines
from app.lab_service import lab_report_service
from app.models import (
    ChatSessionDetail,
    ChatSessionSummary,
    HistoryMessage,
    IngestResponse,
    LabReportRequest,
    LabReportResponse,
    PrescriptionAnalysisResponse,
    QueryRequest,
    QueryResponse,
    SavedLabReportRecord,
    SavedPrescriptionRecord,
)
from app.prescription_service import prescription_service
from app.rag_engine import rag_engine
from app.vector_store import vector_store
from config import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    if vector_store.get_count() == 0:
        print("Vector database is empty. Running initial ingestion...")
        ingest_guidelines()
    yield


app = FastAPI(title=config.PROJECT_NAME, version=config.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
os.makedirs(frontend_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/")
async def read_index():
    return FileResponse(os.path.join(frontend_path, "index.html"))


@app.post("/api/query", response_model=QueryResponse)
async def query_guidelines(request: QueryRequest):
    try:
        session = history_store.create_or_get_session(request.session_id, request.question, request.language)
        history_store.append_chat_message(
            session["id"],
            HistoryMessage(
                role="user",
                content=request.question,
                timestamp=_timestamp(),
                domain=request.domain,
                language=request.language,
            ),
        )

        response = await rag_engine.get_answer(request.question, request.domain, request.language)
        response.session_id = session["id"]
        response.session_title = session["title"]

        history_store.append_chat_message(
            session["id"],
            HistoryMessage(
                role="assistant",
                content=response.answer,
                timestamp=_timestamp(),
                citations=response.citations,
                confidence=response.confidence,
                guardrail_status=response.guardrail_status,
                disclaimer=response.disclaimer,
                domain=request.domain,
                language=response.language,
            ),
        )
        return response
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/chats", response_model=list[ChatSessionSummary])
async def list_chats():
    return history_store.list_chat_sessions()


@app.get("/api/chats/{session_id}", response_model=ChatSessionDetail)
async def get_chat(session_id: str):
    try:
        return history_store.get_chat_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/api/chats/{session_id}")
async def delete_chat(session_id: str):
    try:
        history_store.delete_chat_session(session_id)
        return {"status": "success", "deleted_id": session_id}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/prescription/analyze", response_model=PrescriptionAnalysisResponse)
async def analyze_prescription(
    file: UploadFile = File(...),
    language: str = Form(config.DEFAULT_LANGUAGE),
):
    try:
        image_bytes = await file.read()
        max_size_bytes = config.MAX_IMAGE_SIZE_MB * 1024 * 1024
        is_valid, reason = guardrails.validate_image(file.content_type or "", len(image_bytes), max_size_bytes)
        if not is_valid:
            raise HTTPException(status_code=400, detail=reason)

        return prescription_service.analyze(
            image_bytes=image_bytes,
            mime_type=file.content_type or "image/jpeg",
            file_name=file.filename or "prescription-image",
            language=language,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/prescriptions", response_model=list[SavedPrescriptionRecord])
async def list_prescriptions():
    return history_store.list_prescriptions()


@app.get("/api/prescriptions/{record_id}", response_model=SavedPrescriptionRecord)
async def get_prescription(record_id: str):
    try:
        return history_store.get_prescription(record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/api/prescriptions/{record_id}")
async def delete_prescription(record_id: str):
    try:
        history_store.delete_prescription(record_id)
        return {"status": "success", "deleted_id": record_id}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/lab-report/interpret", response_model=LabReportResponse)
async def interpret_lab_report(request: LabReportRequest):
    try:
        return lab_report_service.interpret(request.report_text, request.language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/lab-report/analyze-file", response_model=LabReportResponse)
async def interpret_lab_report_file(
    file: UploadFile = File(...),
    language: str = Form(config.DEFAULT_LANGUAGE),
):
    try:
        file_bytes = await file.read()
        content_type = file.content_type or ""

        if content_type == "application/pdf":
            max_size_bytes = config.MAX_PDF_SIZE_MB * 1024 * 1024
            if len(file_bytes) > max_size_bytes:
                raise HTTPException(status_code=400, detail=f"Please upload a PDF smaller than {config.MAX_PDF_SIZE_MB} MB.")
        else:
            is_valid, reason = guardrails.validate_image(content_type, len(file_bytes), config.MAX_IMAGE_SIZE_MB * 1024 * 1024)
            if not is_valid:
                raise HTTPException(status_code=400, detail=reason)

        return lab_report_service.interpret_file(
            file_bytes=file_bytes,
            content_type=content_type,
            file_name=file.filename or "lab-report",
            language=language,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/lab-reports", response_model=list[SavedLabReportRecord])
async def list_lab_reports():
    return history_store.list_lab_reports()


@app.get("/api/lab-reports/{record_id}", response_model=SavedLabReportRecord)
async def get_lab_report(record_id: str):
    try:
        return history_store.get_lab_report(record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/api/lab-reports/{record_id}")
async def delete_lab_report(record_id: str):
    try:
        history_store.delete_lab_report(record_id)
        return {"status": "success", "deleted_id": record_id}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/ingest", response_model=IngestResponse)
async def run_ingestion():
    try:
        count = ingest_guidelines()
        return IngestResponse(
            status="success",
            count=count,
            message=f"Successfully ingested {count} chunks into the local knowledge base.",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/domains")
async def get_domains():
    return vector_store.get_domains()


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "vector_db_count": vector_store.get_count(),
        "provider": config.LLM_PROVIDER,
        "groq_api": "configured" if config.GROQ_API_KEY else "missing",
        "domains": vector_store.get_domains(),
        "image_upload_max_mb": config.MAX_IMAGE_SIZE_MB,
        "default_language": config.DEFAULT_LANGUAGE,
        "languages": ["English", "Hindi", "Telugu", "Tamil", "Kannada", "Malayalam", "Bengali"],
    }


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)
