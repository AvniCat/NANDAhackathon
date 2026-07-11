"""Core intent → Structured Requirement Card extraction."""
from __future__ import annotations
import json
import re
from typing import Any

from app.llm import chat, LLMError

MODEL_VERSION = "needtranslator-v0.1"

SYSTEM_PROMPT = """You are NeedTranslator, a buyer-side marketplace skill. Your job is
to convert a natural-language buyer intent into a strict-schema JSON object called a
Structured Requirement Card. This card will be consumed by an AI shopping agent.

You MUST return ONLY valid JSON, no prose, no code fences, no explanation.
The JSON must match this schema exactly:

{
  "canonical_intent": string,   // one clean sentence restating what the buyer wants
  "category_tags": [string],    // 1-3 product/service categories (specific, not "electronics")
  "must_haves": [string],       // hard constraints that any match must satisfy
  "nice_to_haves": [string],    // soft preferences used for ranking
  "disqualifiers": [string],    // items that superficially match keywords but would FAIL the buyer
  "search_queries": [string],   // 3-5 ready-to-paste marketplace search strings
  "entities": {
    "quantity": {value: number, unit: string} | null,
    "duration": {value: number, unit: string} | null,
    "budget":   {value: number, currency: string} | null,
    "location": string | null,
    "deadline": string | null,
    "domain":   string | null
  },
  "confidence": number,         // 0.0 to 1.0, honest — LOW when intent is vague/ambiguous
  "flags": [string]             // any of: ambiguous_intent, contradiction, multi_object,
                                //         out_of_scope, hidden_constraint, language_mixed,
                                //         time_pressured, budget_constrained, low_confidence
}

Rules:
- If the intent is genuinely ambiguous ("something nice"), set confidence < 0.4 and add
  ambiguous_intent to flags. Do not invent constraints to fill the card.
- If two constraints conflict ("cheap luxury"), add contradiction flag.
- If the buyer wants multiple distinct things, add multi_object flag and expand
  category_tags accordingly.
- If the request is infeasible (impossible price for a category), add out_of_scope.
- Extract implicit disqualifiers ("wife hates diesel" → disqualifier "diesel fuel").
- If the input mixes English + another language, add language_mixed but still extract.
- If a budget cap is present, add budget_constrained.
- If a deadline is present, add time_pressured and populate entities.deadline.
- If confidence < 0.5, add low_confidence.
- disqualifiers must be MEANINGFUL — items that a naive keyword search would falsely return.

Be conservative. When in doubt, add a flag rather than invent structure.
"""


def _strip_code_fences(text: str) -> str:
    """LLMs sometimes wrap JSON in ```json ... ``` even when told not to."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _coerce_card(raw: dict) -> dict:
    """Fill in defaults for a partial card so downstream code doesn't crash."""
    defaults = {
        "canonical_intent": "",
        "category_tags": [],
        "must_haves": [],
        "nice_to_haves": [],
        "disqualifiers": [],
        "search_queries": [],
        "entities": {
            "quantity": None, "duration": None, "budget": None,
            "location": None, "deadline": None, "domain": None,
        },
        "confidence": 0.0,
        "flags": [],
    }
    for k, v in defaults.items():
        raw.setdefault(k, v)
    # Ensure entities is a dict
    if not isinstance(raw.get("entities"), dict):
        raw["entities"] = defaults["entities"]
    else:
        for k, v in defaults["entities"].items():
            raw["entities"].setdefault(k, v)
    # Coerce confidence to float in [0, 1]
    try:
        raw["confidence"] = max(0.0, min(1.0, float(raw["confidence"])))
    except (TypeError, ValueError):
        raw["confidence"] = 0.0
    return raw


def translate(intent: str) -> dict:
    """Turn a raw natural-language intent into a Structured Requirement Card."""
    if not intent or not intent.strip():
        return _coerce_card({
            "canonical_intent": "",
            "confidence": 0.0,
            "flags": ["ambiguous_intent", "low_confidence"],
        })

    prompt = f"BUYER INTENT: {intent.strip()}\n\nReturn the Structured Requirement Card JSON."
    try:
        raw = chat(prompt, system=SYSTEM_PROMPT, json_mode=True)
    except LLMError as e:
        # Graceful degradation: return a failure card the agent can act on
        return _coerce_card({
            "canonical_intent": intent.strip(),
            "confidence": 0.0,
            "flags": ["llm_unavailable", "low_confidence"],
            "must_haves": [f"LLM error: {e}"],
        })

    raw = _strip_code_fences(raw)
    try:
        card = json.loads(raw)
    except json.JSONDecodeError:
        return _coerce_card({
            "canonical_intent": intent.strip(),
            "confidence": 0.0,
            "flags": ["parser_error", "low_confidence"],
            "must_haves": [f"Malformed model output: {raw[:200]}"],
        })

    card = _coerce_card(card)
    # Auto-add low_confidence flag if confidence is < 0.5 and flag not already set
    if card["confidence"] < 0.5 and "low_confidence" not in card["flags"]:
        card["flags"].append("low_confidence")
    return card


SUGGEST_SYSTEM = """You are the NeedTranslator match-suggestion helper. Given a Structured
Requirement Card, propose 4 differentiated GENERIC product categories that a buyer
could search for on a real marketplace. Each match will be turned into a search-link on
Amazon India, Flipkart, and Google Shopping — the buyer then sees actual current
listings themselves.

CRITICAL ANTI-HALLUCINATION RULES:
- Every `product_name` MUST be a generic, searchable product category description that
  Amazon India / Flipkart already have inventory for. Examples:
    OK  : "Commercial Refrigerated Seafood Display Counter"
    OK  : "Over-Ear Noise-Cancelling Headphones"
    OK  : "Walk-In Chicken Coop with Galvanized Wire"
    BAD : "Blue Star XR-500 Model 2024"   (invents a specific SKU)
    BAD : "Premium Cedar Heavy-Duty Walk-In Chicken Coop"  (invents a specific product)
- Do NOT invent specific brand names, model numbers, or SKU codes. Only use brand names
  that are DEFINITELY real and dominant in India (Amazon Basics, Boat, Sony, Blue Star,
  Samsung, Whirlpool, etc.) — and only if the buyer clearly needs a brand.
- Each `product_name` must survive a marketplace search: if a buyer pastes it into
  amazon.in and gets zero relevant results, you failed.

Each match must also:
- Match all must_haves and violate none of the disqualifiers
- Differ from the others — different form factors, price bands, or use cases
- Include a realistic price range in Indian Rupees (INR)
- Include a one-line "why_match" grounded in specific must_haves it satisfies

Return ONLY valid JSON matching this schema:
{
  "matches": [
    {
      "product_name": string,          // generic searchable category — NOT a specific SKU
      "category": string,               // broader category, uppercase-suitable
      "price_range_inr": {"min": number, "max": number},
      "why_match": string,
      "typical_seller_types": [string],
      "match_score": number             // 0.0 to 1.0
    }
  ]
}

Rules:
- Exactly 4 matches unless the card is too ambiguous, in which case return an empty matches array.
- No prose, no explanation, no code fences.
- Price ranges must be in INR. Convert if the card implies another currency.
"""


def _add_marketplace_search_urls(matches: list[dict]) -> list[dict]:
    """For each match, add safe marketplace-search URLs (not specific product URLs).

    Search URLs are hallucination-proof — they always return real current inventory,
    and the buyer picks from what's actually available on each marketplace.
    """
    import urllib.parse
    for m in matches:
        name = str(m.get("product_name") or "").strip()
        if not name:
            m["marketplace_search_urls"] = []
            continue
        q = urllib.parse.quote_plus(name)
        m["marketplace_search_urls"] = [
            {"marketplace": "Amazon India",   "url": f"https://www.amazon.in/s?k={q}"},
            {"marketplace": "Flipkart",       "url": f"https://www.flipkart.com/search?q={q}"},
            {"marketplace": "Google Shopping", "url": f"https://www.google.com/search?tbm=shop&q={q}"},
        ]
    return matches


def suggest_matches(card: dict) -> list[dict]:
    """Given a Structured Requirement Card, return 4 illustrative product matches with
    hallucination-proof marketplace-search deep-links."""
    import json
    prompt = f"REQUIREMENT CARD:\n{json.dumps(card, indent=2)}\n\nReturn the matches JSON."
    try:
        raw = chat(prompt, system=SUGGEST_SYSTEM, json_mode=True)
    except LLMError:
        return []
    raw = _strip_code_fences(raw)
    try:
        parsed = json.loads(raw)
        matches = parsed.get("matches", []) or []
    except json.JSONDecodeError:
        return []
    return _add_marketplace_search_urls(matches)


CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "canonical_intent": {"type": "string"},
        "category_tags":    {"type": "array", "items": {"type": "string"}},
        "must_haves":       {"type": "array", "items": {"type": "string"}},
        "nice_to_haves":    {"type": "array", "items": {"type": "string"}},
        "disqualifiers":    {"type": "array", "items": {"type": "string"}},
        "search_queries":   {"type": "array", "items": {"type": "string"}},
        "entities":         {"type": "object"},
        "confidence":       {"type": "number", "minimum": 0, "maximum": 1},
        "flags":            {"type": "array", "items": {"type": "string"}},
    },
    "required": ["canonical_intent", "category_tags", "must_haves",
                 "confidence", "flags"],
}
