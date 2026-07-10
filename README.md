# NeedTranslator

**Buyer-side marketplace skill for the NANDA hackathon.** Turns fuzzy natural-language buyer intent into a strict-schema Structured Requirement Card that a downstream marketplace agent can act on — with a built-in 12-case adversarial validator so agents can verify extraction quality before committing.

- **Skill spec**: [`SKILL.md`](./SKILL.md)
- **Live demo**: `https://needtranslator.onrender.com` *(pending Render deploy)*
- **Author**: Avni Singh · [@AvniCat](https://github.com/AvniCat)

## What it does

Marketplace buyers describe things in messy natural language. Marketplaces index by SKU, category, and structured attributes. NeedTranslator bridges the gap with LLM extraction wrapped in strict schema validation, deterministic post-processing, and adversarial testing.

**Input**: `"I need something for my restaurant that keeps 100 oysters fresh for 3 days"`
**Output**: Structured Requirement Card with `must_haves`, `nice_to_haves`, `disqualifiers`, `search_queries`, extracted entities, confidence, and warning flags.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Interactive demo page |
| GET | `/health` | Liveness probe |
| GET | `/providers` | LLM provider status (Gemini + Ollama) |
| POST | `/translate` | `{intent}` → Structured Requirement Card |
| POST | `/validate` | Run all 12 adversarial test cases + return scorecard |
| GET | `/validate/cases` | List the adversarial test cases |
| GET | `/schema` | JSON Schema for the Card |

## Run locally

```bash
git clone https://github.com/AvniCat/NANDAhackathon
cd NANDAhackathon

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# → paste your GEMINI_API_KEY (free from https://aistudio.google.com)

uvicorn app.main:app --reload --port 8000
# → open http://localhost:8000
```

## Stack

- Python 3.11 + FastAPI
- Google Gemini `gemini-flash-lite-latest` (primary LLM, free tier)
- Ollama `llama3.2:3b` (local fallback)
- Vanilla HTML/CSS/JS website served at `/`

No dataset training required — extraction is prompt-engineered against Gemini's pretrained model with a strict output schema and Pydantic validation as a second gate.

## Adversarial validator

12 hand-crafted hostile test cases across 10 failure classes: ambiguous, contradictory, multi-object, out-of-scope, very-short, very-long, mixed-language, hidden-constraint, time-pressured, domain-jargon, sarcasm-negation. Each case has an expected behavior; the validator grades per-case verdict (passed / partial / failed), aggregate accuracy, per-class precision, and confidence-calibration score.

Run it:
```bash
curl -X POST https://needtranslator.onrender.com/validate
```

## Deploy your own

The repo includes `render.yaml` — connect it to render.com, add `GEMINI_API_KEY` as an environment variable, done.

## License

MIT
