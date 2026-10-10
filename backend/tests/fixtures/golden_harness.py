"""
Harnais d'évaluation du golden dataset.

Construit la fiche que le pipeline transmettrait au Quality Gate à partir d'un golden case :
- les champs structurés du cas (`funding_details`, `eligibility_criteria`) sont transmis
  lorsqu'ils existent dans le cas source ;
- les montants sont extraits par l'AmountEngine depuis `raw_content`, comme le fait le normalizer ;
- les valeurs `expected` ne sont jamais utilisées comme entrées, sauf `deadline`, `is_recurring` et `country`
  (faits de source / configuration de source que le normalizer générique n'extrait pas du texte brut).

Les golden cases datent de 2025 : `frozen_reference_date` fige l'horloge du gate à une date cohérente
avec le jeu (après la clôture du 31/03/2025 du cas D01, avant l'échéance du 15/07/2025 du cas A08),
pour que les résultats ne dérivent pas avec le temps.
"""
from contextlib import contextmanager
from datetime import date

from app.services.amount_engine import AmountEngine
from app.services.content_classifier import ContentClassifier
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import sanitize_text

GOLDEN_REFERENCE_DATE = date(2025, 6, 1)


class _FrozenDate(date):
    @classmethod
    def today(cls):
        return GOLDEN_REFERENCE_DATE


@contextmanager
def frozen_reference_date():
    import app.services.device_quality as device_quality

    original = device_quality.date
    device_quality.date = _FrozenDate
    try:
        yield
    finally:
        device_quality.date = original


def extraction_text(case: dict) -> str:
    """Texte fourni à l'AmountEngine : titre + corps nettoyés par sanitize_text, comme dans le normalizer."""
    return sanitize_text(f"{case['expected'].get('title') or ''} {case['raw_content']}")


def build_device(case: dict) -> dict:
    expected = case["expected"]
    text = case["raw_content"]
    amounts = AmountEngine().extract(extraction_text(case), country=expected.get("country", ""))
    recurring = bool(expected.get("is_recurring"))
    return {
        "title": expected.get("title") or case["id"],
        "source_url": case["source_url"],
        "short_description": text[:200],
        "full_description": text,
        "funding_details": case.get("funding_details", ""),
        "eligibility_criteria": case.get("eligibility_criteria", ""),
        "country": expected.get("country", ""),
        "close_date": expected.get("deadline"),
        "status": "recurring" if recurring else "open",
        "is_recurring": recurring,
        "amount_min": amounts.amount_min,
        "amount_max": amounts.amount_max,
        "currency": amounts.currency,
        "_program_budget": amounts.program_budget,
    }


def evaluate_case(case: dict) -> dict:
    """Résultat brut (gate + classifier + amount engine) pour un golden case."""
    device = build_device(case)
    with frozen_reference_date():
        decision = DeviceQualityGate().evaluate(device)
    content = ContentClassifier().classify(device)
    amounts = AmountEngine().extract(extraction_text(case), country=case["expected"].get("country", ""))
    return {"device": device, "decision": decision, "content": content, "amounts": amounts}


def check_case(case: dict) -> list[str]:
    """Liste des écarts entre le résultat et `expected` (vide = PASS). Comparaisons strictes."""
    expected = case["expected"]
    result = evaluate_case(case)
    decision, content, amounts = result["decision"], result["content"], result["amounts"]
    errors: list[str] = []

    published = decision.validation_status == "auto_published"
    if published != expected["should_publish"]:
        errors.append(f"publish: expected={expected['should_publish']} got={published} ({decision.quality_state} {decision.reasons})")
    if decision.quality_state != expected["quality_state"]:
        errors.append(f"quality_state: expected={expected['quality_state']} got={decision.quality_state} {decision.reasons}")
    if content.content_type.value != expected["content_nature"]:
        errors.append(f"content_nature: expected={expected['content_nature']} got={content.content_type.value}")
    for field in ("amount_min", "amount_max"):
        if getattr(amounts, field) != expected.get(field):
            errors.append(f"{field}: expected={expected.get(field)} got={getattr(amounts, field)}")
    if expected.get("amount_max") is not None or expected.get("amount_min") is not None:
        if amounts.currency != expected["currency"]:
            errors.append(f"currency: expected={expected['currency']} got={amounts.currency}")
    if amounts.amount_type.value != expected["amount_type"]:
        errors.append(f"amount_type: expected={expected['amount_type']} got={amounts.amount_type.value}")
    return errors
