# FairPrice

**Buyer-side marketplace skill that tells a buyer whether a listing's asking price is fair.**

## What it does

Given a marketplace listing, FairPrice returns a price verdict — `fair`, `overpriced`, `suspiciously_low`, or `insufficient_data` — with confidence, a peer-comparable set, and the underlying distribution stats. Designed to be called by an AI agent acting on behalf of a buyer before it commits to a purchase.

## API contract

Base URL: `https://fairprice-nanda.onrender.com` *(going live shortly)*

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe. |
| POST | `/appraise` | Body: `{listing_id, category, price, currency, quantity, seller_id, timestamp}`. Returns the verdict + evidence. |
| GET | `/comparables?category=<>&price=<>` | Returns comparable recent transactions used by the model. |
| POST | `/validate` | Adversarial validator — accepts a batch of listings with known ground truth, returns per-listing correctness. |

## Example call

```bash
curl -X POST https://fairprice-nanda.onrender.com/appraise \
  -H "Content-Type: application/json" \
  -d '{
    "listing_id": "L-9821",
    "category": "frozen_shrimp_500g",
    "price": 1899,
    "currency": "INR",
    "quantity": 100,
    "seller_id": "S-004",
    "timestamp": "2026-07-10T14:00:00Z"
  }'
```

**Example response:**
```json
{
  "verdict": "overpriced",
  "confidence": 0.82,
  "reference_price_median": 1420,
  "reference_price_p10_p90": [1210, 1610],
  "n_comparables_used": 47,
  "reasoning": "Asking price is 33.7% above 90th-percentile of comparable listings from the last 30 days across 12 sellers.",
  "comparables_sample": [
    {"listing_id": "L-8811", "price": 1385, "seller_id": "S-001", "days_ago": 3},
    {"listing_id": "L-8945", "price": 1450, "seller_id": "S-017", "days_ago": 6}
  ]
}
```

## Verdicts

- `fair` — price within 25th–75th percentile of comparables
- `overpriced` — price above 90th percentile
- `suspiciously_low` — price below 10th percentile (may indicate scam or defect)
- `insufficient_data` — fewer than 5 comparables in the reference set

## Adversarial validator

The `/validate` endpoint accepts a batch of listings labeled with ground-truth fairness (built from held-out marketplace data + intentionally seeded outliers). Returns per-listing correctness plus aggregate accuracy, precision-per-verdict, and calibration of confidence scores. This lets NANDA verify the skill's robustness against manipulated inputs (thin markets, price-anchor attacks, single-seller monopolies).

## Architecture

- **Comparables index:** aggregated marketplace transaction history, refreshed hourly
- **Verdict logic:** non-parametric percentile match on category + timestamp window + quantity-scaled price
- **Confidence:** inverse of comparable-set variance, capped by sample size
- **Deployment:** Python 3.11 + FastAPI on Render (free tier), auto-deploy from `main` branch

## Repository

<https://github.com/AvniCat/NANDAhackathon>

## Author

Avni Singh · `neeraj.invincible@gmail.com`

## Tags

`marketplace`, `buyer-side`, `price-benchmarking`, `procurement`, `comparable-transactions`, `market-analysis`, `trust`, `adversarial-validator`, `nanda-hackathon`
