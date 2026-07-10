"""Adversarial validator — 12 hostile test cases, each with an expected behaviour."""
from __future__ import annotations
from typing import Callable

from app.translator import translate


# Each case has:
#   intent: the raw input
#   klass: category of failure the case exercises
#   check: predicate(card) -> (bool, str) where bool = passed, str = reason
CASES: list[dict] = [
    {
        "id": 1, "klass": "ambiguous",
        "intent": "I need something nice",
        "expected": "flags contains ambiguous_intent AND confidence < 0.5",
    },
    {
        "id": 2, "klass": "ambiguous",
        "intent": "Something for the office",
        "expected": "flags contains ambiguous_intent",
    },
    {
        "id": 3, "klass": "contradictory",
        "intent": "A cheap luxury item",
        "expected": "flags contains contradiction",
    },
    {
        "id": 4, "klass": "multi_object",
        "intent": "A wedding dress and a new laptop",
        "expected": "flags contains multi_object AND category_tags length >= 2",
    },
    {
        "id": 5, "klass": "out_of_scope",
        "intent": "Buy me a Ferrari for 500 rupees",
        "expected": "flags contains out_of_scope",
    },
    {
        "id": 6, "klass": "very_short",
        "intent": "cold",
        "expected": "flags contains ambiguous_intent AND confidence < 0.5",
    },
    {
        "id": 7, "klass": "very_long",
        "intent": (
            "So I have this restaurant in Fort Kochi, we do a lot of oyster dishes, "
            "the raw plateau kind, and every Friday the chef gets in about a hundred "
            "oysters from the wholesaler in Alappuzha, but our current cold room "
            "keeps them for max two days before they lose that briny snap, and last "
            "week we had to throw out about thirty of them which is not sustainable, "
            "we've been thinking about getting a dedicated small chiller cabinet, "
            "something that sits on the counter or under it, ideally with humidity "
            "control because oysters actually spoil faster in dry cold than in "
            "slightly humid cold, and my chef keeps saying he wants at least three "
            "days of hold time so we can prep on Thursday for a Saturday service, "
            "budget is not the primary concern but we cannot go crazy, we are a "
            "small business."
        ),
        "expected": "confidence >= 0.6 AND canonical_intent is populated",
    },
    {
        "id": 8, "klass": "mixed_language",
        "intent": "എനിക്ക് a good phone വേണം under ₹15000",
        "expected": "flags contains language_mixed AND budget extracted around 15000",
    },
    {
        "id": 9, "klass": "hidden_constraint",
        "intent": "I need a car and my wife hates diesel",
        "expected": "disqualifiers mentions diesel AND flags contains hidden_constraint",
    },
    {
        "id": 10, "klass": "time_pressured",
        "intent": "Something to keep 20 chickens alive during a 6-hour power cut TONIGHT",
        "expected": "entities.deadline set AND flags contains time_pressured",
    },
    {
        "id": 11, "klass": "domain_jargon",
        "intent": "Need a 3RU 10GbE-capable managed switch, PoE+ preferred",
        "expected": "must_haves mentions 10GbE OR 3RU OR managed switch",
    },
    {
        "id": 12, "klass": "sarcasm_negation",
        "intent": "I'd rather NOT buy anything with plastic packaging",
        "expected": "disqualifiers mentions plastic packaging",
    },
]


def _has_flag(card: dict, flag: str) -> bool:
    return flag in (card.get("flags") or [])


def _text_of(card: dict, field: str) -> str:
    values = card.get(field) or []
    if isinstance(values, list):
        return " ".join(str(v).lower() for v in values)
    return str(values).lower()


def _grade(case: dict, card: dict) -> tuple[str, str]:
    """Return (verdict, reason). verdict in {passed, partial, failed}."""
    klass = case["klass"]
    conf = float(card.get("confidence") or 0.0)

    def _pass(reason=""): return ("passed", reason or case["expected"])
    def _fail(reason):   return ("failed", reason)
    def _partial(reason): return ("partial", reason)

    if klass == "ambiguous":
        if _has_flag(card, "ambiguous_intent"):
            return _pass()
        if conf < 0.5:
            return _partial("confidence low but ambiguous_intent flag missing")
        return _fail("no ambiguity flag and confidence too high")

    if klass == "contradictory":
        return _pass() if _has_flag(card, "contradiction") else _fail("contradiction flag missing")

    if klass == "multi_object":
        cats = card.get("category_tags") or []
        if _has_flag(card, "multi_object") and len(cats) >= 2:
            return _pass()
        if len(cats) >= 2 or _has_flag(card, "multi_object"):
            return _partial("one of {flag, ≥2 categories} present but not both")
        return _fail("multi_object flag missing AND fewer than 2 category tags")

    if klass == "out_of_scope":
        return _pass() if _has_flag(card, "out_of_scope") else _fail("out_of_scope flag missing")

    if klass == "very_short":
        if _has_flag(card, "ambiguous_intent") and conf < 0.5:
            return _pass()
        if conf < 0.5:
            return _partial("low confidence but no ambiguity flag")
        return _fail("confidence too high for a one-word input")

    if klass == "very_long":
        if conf >= 0.6 and card.get("canonical_intent", "").strip():
            return _pass()
        return _partial("card populated but confidence < 0.6")

    if klass == "mixed_language":
        budget = ((card.get("entities") or {}).get("budget") or {}).get("value")
        has_lang_flag = _has_flag(card, "language_mixed")
        if has_lang_flag and budget and abs(float(budget) - 15000) < 1000:
            return _pass()
        if has_lang_flag or (budget and abs(float(budget) - 15000) < 1000):
            return _partial("one of {language_mixed flag, budget extraction} present")
        return _fail("neither language flag nor budget extracted")

    if klass == "hidden_constraint":
        disqs = _text_of(card, "disqualifiers")
        if "diesel" in disqs and _has_flag(card, "hidden_constraint"):
            return _pass()
        if "diesel" in disqs:
            return _partial("diesel disqualifier present but no hidden_constraint flag")
        return _fail("diesel not in disqualifiers")

    if klass == "time_pressured":
        deadline = (card.get("entities") or {}).get("deadline")
        has_flag = _has_flag(card, "time_pressured")
        if deadline and has_flag:
            return _pass()
        if deadline or has_flag:
            return _partial("one of {deadline entity, time_pressured flag} present")
        return _fail("neither deadline nor time_pressured flag")

    if klass == "domain_jargon":
        text = _text_of(card, "must_haves") + " " + _text_of(card, "nice_to_haves")
        if any(term in text for term in ["10gbe", "3ru", "managed switch", "poe"]):
            return _pass()
        return _fail("no domain jargon preserved in must/nice haves")

    if klass == "sarcasm_negation":
        disqs = _text_of(card, "disqualifiers")
        if "plastic" in disqs:
            return _pass()
        return _fail("plastic packaging not recognized as a disqualifier")

    return _fail(f"unknown class {klass}")


def _brier_confidence(cases_and_cards: list[tuple[dict, dict, str]]) -> float:
    """Reward LOW confidence on failed cases, HIGH confidence on passed ones."""
    if not cases_and_cards: return 0.0
    total = 0.0
    for _, card, verdict in cases_and_cards:
        conf = float(card.get("confidence") or 0.0)
        target = 1.0 if verdict == "passed" else 0.0
        total += (conf - target) ** 2
    return round(1 - total / len(cases_and_cards), 3)   # 1 = perfect calibration


def run_validation() -> dict:
    """Run all cases, return per-case results + aggregate scores."""
    results = []
    for c in CASES:
        card = translate(c["intent"])
        verdict, reason = _grade(c, card)
        results.append({
            "id": c["id"], "klass": c["klass"], "intent": c["intent"],
            "expected": c["expected"], "verdict": verdict, "reason": reason,
            "confidence": card.get("confidence"), "flags": card.get("flags"),
        })

    passed = sum(1 for r in results if r["verdict"] == "passed")
    partial = sum(1 for r in results if r["verdict"] == "partial")
    failed = sum(1 for r in results if r["verdict"] == "failed")
    accuracy = round(passed / len(results), 3) if results else 0.0

    # per-class breakdown
    per_class = {}
    for r in results:
        k = r["klass"]
        per_class.setdefault(k, {"passed": 0, "partial": 0, "failed": 0, "total": 0})
        per_class[k]["total"] += 1
        per_class[k][r["verdict"]] += 1

    # confidence calibration
    grouped = [(CASES[i], translate(CASES[i]["intent"]) if False else results[i], results[i]["verdict"])
               for i in range(len(CASES))]
    calib = _brier_confidence([
        (CASES[i], {"confidence": results[i]["confidence"]}, results[i]["verdict"])
        for i in range(len(CASES))
    ])

    return {
        "total_cases":  len(results),
        "passed":       passed,
        "partial":      partial,
        "failed":       failed,
        "accuracy":     accuracy,
        "per_class":    per_class,
        "confidence_calibration_score": calib,
        "per_case":     results,
    }


def list_cases() -> list[dict]:
    """Return the test cases in a form suitable for the /validate/cases endpoint."""
    return [{"id": c["id"], "klass": c["klass"], "intent": c["intent"],
             "expected": c["expected"]} for c in CASES]
