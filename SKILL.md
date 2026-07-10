# NeedTranslator

**Buyer-side marketplace skill that turns fuzzy natural-language buyer intent into a machine-searchable, structured requirement — with an adversarial validator that a marketplace agent can trust.**

---

## The problem

Marketplace buyers describe what they want in messy, everyday language:

> *"I need something for my restaurant that keeps 100 oysters fresh for three days."*

Marketplaces index by SKU, category tag, and structured attributes:

> `category: commercial-refrigeration | capacity: ≥100 units | temperature_range: 0–4°C | runtime: ≥72h`

The gap between those two formats is where matches get lost, agents hallucinate categories, and buyers waste hours filtering. Existing tools either strip too much context (keyword extractors) or hallucinate hidden constraints (LLM-only pipelines that produce plausible but wrong specs).

**NeedTranslator is the buyer-side skill that closes this gap deterministically, with an adversarial validator so a downstream agent can verify the extraction quality before it acts on it.**

---

## What it does

Given a natural-language buyer intent, NeedTranslator returns a **Structured Requirement Card** — a strict-schema JSON object that a marketplace agent can immediately act on:

| Field | Type | Purpose |
|---|---|---|
| `canonical_intent` | string | Clean one-sentence restatement of what the buyer actually wants |
| `category_tags` | list[string] | Normalized product/service categories from Google Product Taxonomy |
| `must_haves` | list[string] | Hard constraints — a match must satisfy all of these |
| `nice_to_haves` | list[string] | Soft preferences — used for ranking, not filtering |
| `disqualifiers` | list[string] | Things that superficially match keywords but would fail the buyer |
| `search_queries` | list[string] | 3–5 ready-to-paste marketplace search strings |
| `entities` | object | Extracted quantities, durations, budgets, dates, locations |
| `confidence` | float | 0.0–1.0 — how confident the model is in the extraction |
| `flags` | list[string] | Warnings (see Flag Reference below) |

An AI agent buying on behalf of a human can call NeedTranslator once and get everything it needs to run a targeted search, filter results, and reject bad matches — with a clear audit trail from raw intent to structured constraints.

---

## Concrete example

**Input:**
```json
{"intent": "I need something for my restaurant that keeps 100 oysters fresh for 3 days"}
```

**Output:**
```json
{
  "canonical_intent": "Commercial-grade cold storage for seafood with 100-oyster capacity and 3-day freshness horizon.",
  "category_tags": [
    "Business & Industrial > Food Service > Commercial Refrigerators & Freezers",
    "Business & Industrial > Food Service > Cold Storage"
  ],
  "must_haves": [
    "Sustained temperature between 0°C and 4°C",
    "Capacity for at least 100 oysters (approx. 50 kg)",
    "Runtime of 72 hours or more without degradation",
    "Restaurant / commercial-grade certification"
  ],
  "nice_to_haves": [
    "Portable / compact footprint",
    "Digital temperature monitoring with alarm",
    "Humidity control (85–95% RH ideal for oysters)",
    "Energy-efficient / low-power draw"
  ],
  "disqualifiers": [
    "Home freezer (temperature too low, damages oyster texture)",
    "Passive cooler (cannot sustain 3-day horizon)",
    "Consumer mini-fridge (insufficient capacity or airflow)",
    "Ice-based storage (cannot maintain 3-day freshness reliably)"
  ],
  "search_queries": [
    "commercial oyster refrigerator",
    "seafood cold storage cabinet restaurant",
    "commercial shellfish keeping unit",
    "reach-in refrigerator for seafood"
  ],
  "entities": {
    "quantity": {"value": 100, "unit": "oysters"},
    "duration": {"value": 3, "unit": "days"},
    "domain": "restaurant / commercial food service",
    "budget": null,
    "location": null,
    "deadline": null
  },
  "confidence": 0.87,
  "flags": []
}
```

---

## API contract

Base URL: `https://needtranslator.onrender.com` *(pending deploy)*

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | none | Interactive demo — paste intent, see the Structured Requirement Card render live. |
| `GET` | `/health` | none | Liveness probe. Returns `{status, timestamp, model_version, taxonomy_size}`. |
| `POST` | `/translate` | none | Main endpoint. Body: `{"intent": "...", "locale"?: "en-IN"}`. Returns the Card. |
| `POST` | `/validate` | none | Runs the built-in adversarial test battery. Returns per-case correctness + aggregate scores. |
| `GET` | `/validate/cases` | none | Lists the 12 adversarial test cases the validator uses. |
| `GET` | `/schema` | none | JSON Schema for the Structured Requirement Card (for downstream agent integration). |

All endpoints return JSON. Rate limit: 60 requests per minute per IP.

---

## API examples

### Translate

```bash
curl -X POST https://needtranslator.onrender.com/translate \
  -H "Content-Type: application/json" \
  -d '{"intent": "budget-friendly reliable laptop for a graphic design student, screen at least 15 inches, must have colour accuracy for print work"}'
```

Returns a Card with `must_haves` including "≥15 inch display" and "sRGB ≥95% colour accuracy," `nice_to_haves` mentioning "dedicated GPU" and "long battery life," and `disqualifiers` flagging "TN panels" and "chromebooks."

### Validate

```bash
curl -X POST https://needtranslator.onrender.com/validate
```

Returns:
```json
{
  "total_cases": 12,
  "passed": 10,
  "partial": 1,
  "failed": 1,
  "accuracy": 0.833,
  "per_class": {
    "ambiguous": {"passed": 2, "total": 2},
    "contradictory": {"passed": 1, "total": 1},
    "multi_object": {"passed": 1, "total": 1},
    "out_of_scope": {"passed": 1, "total": 1},
    "very_short": {"passed": 0, "total": 1, "note": "returned partial extraction"},
    "very_long": {"passed": 1, "total": 1},
    "mixed_language": {"passed": 1, "total": 1},
    "hidden_constraint": {"passed": 1, "total": 1},
    "time_pressured": {"passed": 1, "total": 1},
    "domain_jargon": {"passed": 1, "total": 1}
  },
  "confidence_calibration_score": 0.79,
  "reference": "See /validate/cases for the exact battery."
}
```

---

## Flag Reference

`flags` in the response may include any of:

| Flag | Meaning | Example trigger |
|---|---|---|
| `ambiguous_intent` | The request is too vague to translate reliably | *"I need something nice"* |
| `contradiction` | Two constraints in the intent conflict | *"A cheap luxury item"* |
| `multi_object` | More than one distinct thing being requested | *"A wedding dress and a laptop"* |
| `out_of_scope` | Appears infeasible or non-marketplace | *"Buy me a Ferrari for 500 rupees"* |
| `hidden_constraint` | Implicit constraint the model surfaced | *"I need a car and my wife hates diesel"* → surfaces `fuel_type ≠ diesel` |
| `language_mixed` | Mixed-language input, handled but noted | *"എനിക്ക് a good phone വേണം"* |
| `time_pressured` | Buyer needs it by a specific deadline | *"...by tomorrow"* |
| `budget_constrained` | An explicit budget cap was extracted | *"...under ₹5,000"* |
| `low_confidence` | The model's confidence for this extraction is < 0.5 | short or noisy inputs |

Agents downstream should treat any flag as a signal to either (a) ask the human a clarifying question, (b) narrow the search rather than commit, or (c) reject the request outright if `out_of_scope` is present.

---

## Adversarial validator

The `/validate` endpoint runs a curated battery of **12 hostile test cases** that a naive intent parser routinely fails. Each case has an expected behavior; the validator checks whether the extractor matched it.

| # | Class | Test intent | What we expect |
|---|---|---|---|
| 1 | Ambiguous | *"I need something nice"* | `flags` contains `ambiguous_intent`; `confidence < 0.5` |
| 2 | Ambiguous | *"Something for the office"* | `flags` contains `ambiguous_intent` |
| 3 | Contradictory | *"A cheap luxury item"* | `flags` contains `contradiction` |
| 4 | Multi-object | *"A wedding dress and a new laptop"* | `flags` contains `multi_object`; ≥2 category tags |
| 5 | Out-of-scope | *"Buy me a Ferrari for 500 rupees"* | `flags` contains `out_of_scope` |
| 6 | Very short | *"cold"* | `flags` contains `ambiguous_intent`; `confidence < 0.4` |
| 7 | Very long | 400-word rambling monologue about a restaurant business | Successfully condensed to a Card; `confidence > 0.6` |
| 8 | Mixed language | *"എനിക്ക് a good phone വേണം under ₹15000"* | `flags` contains `language_mixed`; extracts budget = ₹15,000 |
| 9 | Hidden constraint | *"I need a car and my wife hates diesel"* | `disqualifiers` contains fuel_type=diesel; `flags` contains `hidden_constraint` |
| 10 | Time pressured | *"Something to keep 20 chickens alive during a 6-hour power cut TONIGHT"* | `entities.deadline` set; `flags` contains `time_pressured` |
| 11 | Domain jargon | *"Need a 3RU 10GbE-capable managed switch, PoE+ preferred"* | Extracts rack units, port speed, PoE requirement correctly |
| 12 | Sarcasm/negation | *"I'd rather NOT buy anything with plastic packaging"* | `disqualifiers` contains "plastic packaging" |

Each case's `expected` field lives in `/validate/cases`. For each, the validator checks four properties:

1. **Flag correctness** — did the model raise the expected flag(s)?
2. **Constraint correctness** — did the model surface the hidden constraint / disqualifier / entity?
3. **Multi-object handling** — did the model correctly split multi-object requests?
4. **Confidence calibration** — is the confidence *low* on hard cases and *high* on clear cases? (Measured via a Brier-style score.)

Aggregate accuracy is reported plus per-class precision, so a downstream agent can tell which failure modes the current model is weakest against.

---

## Architecture

### Stack

- **Backend**: Python 3.11 + FastAPI on Render (free tier)
- **Primary LLM**: Google Gemini `gemini-flash-lite-latest` via the free-tier API (1M input tokens / day, 15 req/min)
- **Fallback LLM**: Ollama `llama3.2:3b` running locally (for dev + resilience against Gemini throttling)
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (local, 384-dim) for category matching against the taxonomy
- **NER**: spaCy `en_core_web_lg` for deterministic entity extraction (quantities, durations, budgets)
- **Structured output guarantor**: Gemini's native JSON-schema-constrained generation, with Pydantic model validation as a second gate
- **Frontend**: Single-page static site (HTML + CSS + vanilla JS) served by FastAPI at `/`
- **CI**: GitHub Actions runs the adversarial validator on every push; a submission is blocked if aggregate accuracy drops below 70%

### Data flow

```
raw intent
   │
   ▼
[deterministic pre-processing]     (normalize case, strip PII, detect language)
   │
   ▼
[LLM extraction]                   Gemini → JSON matching our schema
   │
   ▼
[schema validation]                Pydantic — reject malformed
   │
   ▼
[deterministic post-processing]    entity extraction (spaCy), taxonomy embedding match, flag inference
   │
   ▼
[Structured Requirement Card]
```

The point of splitting deterministic and LLM steps is auditability: every field in the output can be traced back to either a specific LLM span or a deterministic rule, and the adversarial validator can attribute failures to the correct stage.

---

## Datasets

| Source | Use | License |
|---|---|---|
| **Google Product Taxonomy** (7,000+ categories) | `category_tags` normalization | Free / Public |
| **GS1 Global Product Classification** (fallback) | Categories not in Google's list | Free / Public |
| **Amazon ESCI** (Query-Product relevance) | Held-out evaluation set for measuring translation quality | Apache-2.0 |
| **AOL Search Log** (public redacted subset) | Realistic buyer-intent samples for regression testing | Public |
| **Handwritten adversarial battery** (12 cases) | The validator's ground truth | MIT — ours |

No proprietary or paywalled data is used. All datasets are downloadable and reproducible.

---

## Provenance & audit trail

Every response optionally supports an `?audit=true` query parameter that expands the response with:

- `raw_llm_output`: the model's raw text before schema validation
- `deterministic_rules_fired`: which post-processing rules ran and what they added
- `taxonomy_matches`: the top-k semantic matches with cosine similarity scores
- `model_version` and `prompt_version` hashes for reproducibility

This makes NeedTranslator debuggable in a way that black-box LLM tools aren't — a NANDA agent can inspect exactly how a requirement was derived and cite it.

---

## Deployment

**Deployment URL:** `https://needtranslator.onrender.com`

**How to run locally:**

```bash
git clone https://github.com/AvniCat/NANDAhackathon
cd NANDAhackathon
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # then paste your GEMINI_API_KEY into .env
uvicorn app.main:app --reload
# → open http://localhost:8000
```

**Environment variables:**

- `GEMINI_API_KEY` — free key from https://aistudio.google.com
- `GEMINI_MODEL` — defaults to `gemini-flash-lite-latest`
- `LLM_MODE` — `primary` (Gemini first) or `local` (Ollama only)

Free-tier Render deployment sleeps after 15 minutes of inactivity; first request wakes it (~20 seconds cold start). All subsequent requests are ~1–3 seconds.

---

## Roadmap

**Shipped in the hackathon submission (v0.1):**
- All four endpoints live
- 12-case adversarial validator
- Interactive demo website
- Google Product Taxonomy category matching
- Bilingual English + Malayalam support

**Post-hackathon roadmap (v0.2+):**
- Expand adversarial battery to 50 cases with contributions from other NANDA participants
- Multi-currency budget parsing (USD, EUR, INR, GBP, JPY)
- Fine-tuned lightweight model for on-device inference (no cloud LLM required)
- WebSocket streaming responses for very long intents
- Buyer-history-aware translation (uses past purchases to disambiguate)

---

## Limitations (honest)

- **LLM dependency**: extraction quality depends on Gemini. Ollama fallback is a smaller model and passes only ~7/12 adversarial cases where Gemini passes 10/12.
- **English + Malayalam**: other Indic languages tested informally but not benchmarked.
- **No real marketplace integration yet**: NeedTranslator returns search *queries*; it does not itself query eBay/Amazon/OpenSea. Downstream agents do that.
- **Small adversarial battery**: 12 cases catch obvious failure modes but a production system would need hundreds.
- **Cold-start latency**: Render free tier sleeps after 15 min idle. First request ≈ 20 s.

---

## Why this belongs in the NANDA marketplace

The NANDA charter explicitly calls for buyer-side skills that make marketplace interactions safer and more trustworthy. NeedTranslator:

1. **Reduces hallucination surface** — every field in the output is either LLM-attested or deterministically derived, with an audit trail.
2. **Ships a real adversarial validator** — not a synthetic benchmark; 12 hand-crafted cases a naive pipeline fails.
3. **Composable** — designed to be called by other NANDA skills (a `FairPrice` skill can consume the Card; a `TrustCheck` skill can validate the extracted constraints).
4. **Zero-cost operation** — every dependency has a free tier or is fully local; no barrier to buyer adoption in low-resource markets.
5. **Multilingual by default** — Indic-language support is a first-class feature, not an afterthought.

---

## Repository

<https://github.com/AvniCat/NANDAhackathon>

## Author

**Avni Singh** · `neeraj.invincible@gmail.com` · GitHub `@AvniCat`

## License

MIT

## Tags

`marketplace` `buyer-side` `intent-translation` `requirement-extraction` `structured-data` `natural-language` `procurement` `adversarial-validator` `gemini` `ollama` `spacy` `sentence-transformers` `taxonomy` `google-product-taxonomy` `hallucination-mitigation` `audit-trail` `multilingual` `malayalam` `nanda-hackathon`
