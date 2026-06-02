"""Repere les mots francais non accentues encore visibles dans les fiches."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


VISIBLE_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
VISIBLE_USER_DECISIONS = {None, "publish", "publish_with_caution"}
ACTIONABLE_STATUSES = {"open", "recurring"}
NON_ACTIONABLE_TYPES = {"autre", "institutional_project"}
TEXT_FIELDS = [
    "title",
    "short_description",
    "full_description",
    "eligibility_criteria",
    "eligible_expenses",
    "specific_conditions",
    "required_documents",
    "funding_details",
    "recurrence_notes",
]
JSON_FIELDS = ["content_sections_json", "ai_rewritten_sections_json", "decision_analysis"]

TERMS = [
    "opportunite",
    "opportunites",
    "eligibilite",
    "eligibles",
    "criteres",
    "beneficiaires",
    "demarche",
    "presentation",
    "verifier",
    "confirme",
    "confirmes",
    "confirmees",
    "etre",
    "recevabilite",
    "relayee",
    "reperee",
    "resume",
    "decision",
    "securite",
    "donnees",
    "donnee",
    "creation",
    "creer",
    "creant",
    "generer",
    "generatrices",
    "activites",
    "activite",
    "tres",
    "reelle",
    "reels",
    "reel",
    "fenetre",
    "cloture",
    "depot",
    "depots",
    "depenses",
    "modalites",
    "pieces",
    "developpement",
    "developper",
    "developpent",
    "developpe",
    "developpee",
    "recurrent",
    "recurrente",
    "recurrentes",
    "communiquee",
    "communique",
    "detaille",
    "detailles",
    "detaillees",
    "operationnel",
    "operationnelle",
    "economique",
    "economiques",
    "numerique",
    "numeriques",
    "energie",
    "energies",
    "ecosysteme",
    "capacite",
    "priorite",
    "priorites",
    "maturite",
    "selection",
    "selectionner",
    "editions",
    "edition",
    "acces",
    "age",
    "pret",
    "prets",
    "eleve",
    "elevee",
    "eleves",
    "prive",
    "privee",
    "equipe",
    "equipes",
    "handicapee",
    "handicapees",
    "scolarise",
    "scolarisee",
    "alphabetise",
    "alphabetisee",
    "jusqu'a",
    "Details",
    "Presentation",
    "Demarche",
    "priorises",
    "priorisees",
    "preparables",
    "verifiee",
    "verifiees",
    "finances",
    "financees",
    "presentees",
    "presentes",
    "Region",
    "proposee",
    "proposees",
    "repere",
    "reperee",
    "detaillee",
]

PATTERNS = [(term, re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)) for term in TERMS]
RANGE_A_PATTERN = ("range_a", re.compile(r"\b\d[\d ]*\s+a\s+\d[\d ]*\b", re.IGNORECASE))


def _visible(device: Device) -> bool:
    return (
        device.validation_status in VISIBLE_VALIDATION_STATUSES
        and device.user_quality_decision in VISIBLE_USER_DECISIONS
        and device.status in ACTIONABLE_STATUSES
        and device.device_type not in NON_ACTIONABLE_TYPES
    )


def _visible_json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_visible_json_text(item) for item in value)
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            if key in {"key", "source", "model"}:
                continue
            parts.append(_visible_json_text(item))
        return "\n".join(parts)
    return ""


def _matches(text: str) -> list[str]:
    found: list[str] = []
    for term, pattern in PATTERNS:
        if pattern.search(text):
            found.append(term)
    if RANGE_A_PATTERN[1].search(text):
        found.append(RANGE_A_PATTERN[0])
    return found


async def run() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).order_by(Device.updated_at.desc().nullslast()))).scalars().all()

    for device in devices:
        if not _visible(device):
            continue
        field_matches: dict[str, list[str]] = {}
        for field in TEXT_FIELDS:
            value = getattr(device, field)
            if isinstance(value, str):
                matches = _matches(value)
                if matches:
                    field_matches[field] = matches
        for field in JSON_FIELDS:
            matches = _matches(_visible_json_text(getattr(device, field)))
            if matches:
                field_matches[field] = matches
        if field_matches:
            rows.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "country": device.country,
                    "matches": field_matches,
                }
            )

    return {"visible_residuals": len(rows), "items": rows[:120]}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
