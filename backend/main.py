from fastapi import FastAPI

from backend.config import settings

app = FastAPI(title="RetailMind API", version="0.1.0")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "env": settings.app_env,
        "version": "0.1.0",
    }
