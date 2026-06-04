import uuid
from datetime import datetime
from pathlib import Path

import httpx
import psycopg
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import backend.analytics.agent as analytics_agent
import backend.documents.agent as document_agent
import backend.uploads.agent as uploads_agent
import backend.router as router
from backend.config import settings
from backend.uploads.db import list_datasets

app = FastAPI(title="RetailMind API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ── Analytics models ───────────────────────────────────────────────────────────

class AnalyticsRequest(BaseModel):
    question: str


class AnalyticsResponse(BaseModel):
    question: str
    sql: str
    columns: list[str]
    rows: list[list]
    answer: str


# ── Document models ────────────────────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    document_id: int
    filename: str
    original_filename: str
    chunk_count: int
    status: str


class DocumentQueryRequest(BaseModel):
    question: str


class DocumentQueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[str]


# ── Dataset models ────────────────────────────────────────────────────────────

class DatasetUploadResponse(BaseModel):
    dataset_id: int
    original_filename: str
    row_count: int
    skipped_count: int
    status: str


class DatasetListItem(BaseModel):
    dataset_id: int
    original_filename: str
    row_count: int | None
    skipped_count: int
    upload_date: datetime


# ── Chat models ───────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    route: str
    answer: str
    sql: str | None = None
    columns: list[str] | None = None
    rows: list[list] | None = None
    sources: list[str] | None = None


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "env": settings.app_env,
        "version": "0.1.0",
    }


# ── Analytics ──────────────────────────────────────────────────────────────────

@app.post("/analytics", response_model=AnalyticsResponse)
def analytics(req: AnalyticsRequest):
    llm = analytics_agent.get_llm_provider()
    try:
        result = analytics_agent.run(req.question, llm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"SQL validation failed: {exc}")
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="LLM service unavailable.")
    return AnalyticsResponse(question=req.question, **result)


# ── Documents ──────────────────────────────────────────────────────────────────

@app.post("/documents/upload", response_model=DocumentUploadResponse)
async def documents_upload(file: UploadFile):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    uploads_dir = Path(settings.uploads_path)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    prefix = uuid.uuid4().hex[:8]
    safe_name = f"{prefix}_{file.filename}"
    dest = uploads_dir / safe_name

    contents = await file.read()
    dest.write_bytes(contents)

    try:
        result = document_agent.ingest(dest)
    except psycopg.Error:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="Database unavailable.")
    except httpx.HTTPError:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="LLM service unavailable.")
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

    status = "skipped" if result.get("skipped") else "ingested"
    return DocumentUploadResponse(
        document_id=result["document_id"],
        filename=safe_name,
        original_filename=file.filename,
        chunk_count=result["chunk_count"],
        status=status,
    )


@app.post("/documents/query", response_model=DocumentQueryResponse)
def documents_query(req: DocumentQueryRequest):
    try:
        result = document_agent.run(req.question)
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="LLM service unavailable.")
    return DocumentQueryResponse(question=req.question, **result)


# ── Datasets ───────────────────────────────────────────────────────────────────

@app.post("/datasets/upload", response_model=DatasetUploadResponse)
async def datasets_upload(file: UploadFile):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(
            status_code=400,
            detail="Only .csv and .xlsx files are accepted.",
        )

    uploads_dir = Path(settings.uploads_path)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Safe stored filename: timestamp-uuid prefix preserves the original
    # extension for format detection while preventing collisions and path
    # traversal from user-supplied names.
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    dest = uploads_dir / safe_name

    contents = await file.read()
    dest.write_bytes(contents)

    try:
        result = uploads_agent.ingest(dest, file.filename or safe_name)
    except ValueError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc))
    except psycopg.Error:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="Database unavailable.")
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

    return DatasetUploadResponse(
        dataset_id=result["dataset_id"],
        original_filename=result["original_filename"],
        row_count=result["row_count"],
        skipped_count=result["skipped_count"],
        status="ingested",
    )


@app.get("/datasets", response_model=list[DatasetListItem])
def datasets_list():
    try:
        rows = list_datasets()
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return [DatasetListItem(**row) for row in rows]


# ── Chat ───────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    route = router.classify(req.message)

    if route == "analytics":
        llm = analytics_agent.get_llm_provider()
        try:
            result = analytics_agent.run(req.message, llm)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"SQL validation failed: {exc}")
        except psycopg.Error:
            raise HTTPException(status_code=503, detail="Database unavailable.")
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="LLM service unavailable.")
        return ChatResponse(
            route="analytics",
            answer=result["answer"],
            sql=result["sql"],
            columns=result["columns"],
            rows=result["rows"],
        )

    if route == "document":
        try:
            result = document_agent.run(req.message)
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="LLM service unavailable.")
        return ChatResponse(
            route="document",
            answer=result["answer"],
            sources=result["sources"],
        )

    return ChatResponse(route="unknown", answer=router.UNKNOWN_ANSWER)
