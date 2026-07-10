"""NeedTranslator FastAPI service — buyer-side marketplace skill."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.translator import translate, MODEL_VERSION, CARD_SCHEMA
from app.validator import run_validation, list_cases
from app.llm import provider_status


app = FastAPI(
    title="NeedTranslator",
    description="Buyer-side marketplace skill — turns fuzzy natural-language intent into a "
                "structured, searchable requirement card. NANDA hackathon submission.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TranslateRequest(BaseModel):
    intent: str = Field(..., description="Natural-language buyer intent")
    locale: Optional[str] = Field(default=None, description="BCP-47 locale hint, e.g. en-IN")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "NeedTranslator",
        "model_version": MODEL_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/providers")
def providers() -> dict:
    return provider_status()


@app.post("/translate")
def translate_endpoint(req: TranslateRequest) -> dict:
    if not req.intent or not req.intent.strip():
        raise HTTPException(status_code=400, detail="Empty intent")
    if len(req.intent) > 4000:
        raise HTTPException(status_code=413, detail="Intent too long (max 4000 chars)")
    card = translate(req.intent)
    return card


@app.post("/validate")
def validate_endpoint() -> dict:
    return run_validation()


@app.get("/validate/cases")
def validate_cases() -> dict:
    return {"cases": list_cases(), "count": len(list_cases())}


@app.get("/schema")
def schema() -> dict:
    return {"card_schema": CARD_SCHEMA, "version": MODEL_VERSION}


# ---- static website ----
WEBSITE_DIR = Path(__file__).resolve().parent.parent / "website"
if WEBSITE_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEBSITE_DIR)), name="static")

    @app.get("/")
    def home() -> FileResponse:
        return FileResponse(str(WEBSITE_DIR / "index.html"))
