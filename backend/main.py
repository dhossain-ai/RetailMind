import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import backend.analytics.agent as agent
from backend.config import settings

app = FastAPI(title="RetailMind API", version="0.1.0")


class AnalyticsRequest(BaseModel):
    question: str


class AnalyticsResponse(BaseModel):
    question: str
    sql: str
    columns: list[str]
    rows: list[list]
    answer: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "env": settings.app_env,
        "version": "0.1.0",
    }


@app.post("/analytics", response_model=AnalyticsResponse)
def analytics(req: AnalyticsRequest):
    llm = agent.get_llm_provider()
    try:
        result = agent.run(req.question, llm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"SQL validation failed: {exc}")
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="LLM service unavailable.")
    return AnalyticsResponse(question=req.question, **result)
