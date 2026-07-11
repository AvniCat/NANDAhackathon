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

from app.translator import translate, suggest_matches, MODEL_VERSION, CARD_SCHEMA
from app.validator import run_validation, list_cases
from app.llm import provider_status, chat as llm_chat, LLMError


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


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list,
                                        description="Full conversation history so far")


CHAT_SYSTEM = """You are the NeedTranslator conversational assistant. A buyer is telling
you what they want to buy — often vaguely. Your job:

- Ask ONE targeted clarifying question at a time when the request is too vague to translate.
- When you have enough detail, produce a Structured Requirement Card as strict JSON,
  matching the schema NeedTranslator uses (canonical_intent, category_tags, must_haves,
  nice_to_haves, disqualifiers, search_queries, entities, confidence, flags).
- Keep replies conversational and warm — you are helping a real buyer, not lecturing.
- Reply format:
    Turn 1..N (still gathering): 1–2 sentence conversational reply ending in ONE clarifying
                                 question. NO JSON.
    Final turn (ready): a short conversational preamble + the JSON card in a fenced code
                        block like ```json\n{...}\n```

Never fabricate details the buyer didn't share. If they say "cheap laptop", ask about
budget or use case. If they say "something nice for my mom", ask about her interests
or occasion. Never ask more than one question at a time."""


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


class SuggestRequest(BaseModel):
    intent: Optional[str] = Field(default=None, description="Raw buyer intent — will be translated first")
    card: Optional[dict] = Field(default=None, description="Pre-computed Structured Requirement Card")


@app.post("/suggest")
def suggest_endpoint(req: SuggestRequest) -> dict:
    """Return 4 illustrative product matches for a Requirement Card.

    Accepts either a raw intent (will be translated first) or a pre-computed card.
    Marked illustrative — a downstream MatchFinder skill would query real marketplaces.
    """
    if not req.intent and not req.card:
        raise HTTPException(status_code=400, detail="Provide either 'intent' or 'card'")

    card = req.card or translate(req.intent or "")
    if card.get("confidence", 0.0) < 0.3 or "ambiguous_intent" in (card.get("flags") or []):
        return {
            "matches": [],
            "card": card,
            "note": "Intent too ambiguous to suggest matches — clarify first.",
        }

    matches = suggest_matches(card)
    return {
        "matches": matches,
        "card": card,
        "note": (
            "Illustrative matches only. A production NANDA agent would compose this skill "
            "with a downstream MatchFinder that queries real marketplace inventories."
        ),
    }


@app.post("/chat")
def chat_endpoint(req: ChatRequest) -> dict:
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    if len(req.messages) > 30:
        raise HTTPException(status_code=413, detail="conversation too long (max 30 turns)")

    # Flatten history into a single prompt with role markers
    history = "\n\n".join(f"[{m.role.upper()}]\n{m.content}" for m in req.messages)
    prompt = f"CONVERSATION SO FAR:\n\n{history}\n\n[ASSISTANT] Your reply:"

    try:
        reply = llm_chat(prompt, system=CHAT_SYSTEM)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=f"LLM unavailable: {e}")

    # If the reply contains a JSON card, try to extract it
    import re, json as _json
    card = None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", reply, re.DOTALL)
    if m:
        try:
            card = _json.loads(m.group(1))
        except _json.JSONDecodeError:
            card = None

    return {"reply": reply.strip(), "card": card}


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
