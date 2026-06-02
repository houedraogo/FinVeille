"""Liste les candidats de correction d'accents dans les fiches visibles."""

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
FIELDS = [
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

PATTERNS = [
    re.compile(r"\ba l['’][A-Za-zÀ-ÿ]+", re.IGNORECASE),
    re.compile(r"\ba la\b", re.IGNORECASE),
    re.compile(r"\ba prioriser\b", re.IGNORECASE),
    re.compile(r"\ba verifier\b", re.IGNORECASE),
    re.compile(r"\ba confirmer\b", re.IGNORECASE),
    re.compile(r"\ba preparer\b", re.IGNORECASE),
    re.compile(r"\ba deposer\b", re.IGNORECASE),
    re.compile(r"\ba utiliser\b", re.IGNORECASE),
    re.compile(r"\ba jour\b", re.IGNORECASE),
]


def _visible(device: Device) -> bool:
    return (
        device.validation_status in VISIBLE_VALIDATION_STATUSES
        and device.user_quality_decision in VISIBLE_USER_DECISIONS
        and device.status in ACTIONABLE_STATUSES
        and device.device_type not in NON_ACTIONABLE_TYPES
    )


def _matches(text: str) -> list[str]:
    found: list[str] = []
    for pattern in PATTERNS:
        found.extend(match.group(0) for match in pattern.finditer(text))
    return sorted(set(found))


async def run() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).order_by(Device.updated_at.desc().nullslast()))).scalars().all()

    for device in devices:
        if not _visible(device):
            continue
        field_matches: dict[str, list[str]] = {}
        for field in FIELDS:
            value = getattr(device, field)
            if not isinstance(value, str):
                continue
            matches = _matches(value)
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

    return {"visible_candidates": len(rows), "items": rows[:120]}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
