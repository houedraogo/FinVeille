"""Corrige les derniers résidus d'accents visibles signalés par les audits."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


TARGET_IDS = {
    UUID("45fd53fe-9c14-4ac9-9286-784c90e360ec"),
    UUID("a6d02f0f-5fdf-411c-8aae-560650b57dca"),
    UUID("4e9e7de8-e0e9-4997-90d3-04f79f0001a3"),
}

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

REPLACEMENTS = [
    (re.compile(r"\bA l([’'])", re.UNICODE), r"À l\1"),
    (re.compile(r"\ba l([’'])", re.IGNORECASE | re.UNICODE), r"à l\1"),
    (re.compile(r"\ba verifier\b", re.IGNORECASE), "à vérifier"),
    (re.compile(r"\ba confirmer\b", re.IGNORECASE), "à confirmer"),
    (re.compile(r"\ba preparer\b", re.IGNORECASE), "à préparer"),
    (re.compile(r"\ba deposer\b", re.IGNORECASE), "à déposer"),
    (re.compile(r"\bPresentation\b"), "Présentation"),
    (re.compile(r"\bpresentation\b"), "présentation"),
    (re.compile(r"\bDemarche\b"), "Démarche"),
    (re.compile(r"\bdemarche\b"), "démarche"),
    (re.compile(r"\beligibilite\b", re.IGNORECASE), "éligibilité"),
    (re.compile(r"\bcriteres\b", re.IGNORECASE), "critères"),
    (re.compile(r"\bverifier\b", re.IGNORECASE), "vérifier"),
    (re.compile(r"\bconfirmees\b", re.IGNORECASE), "confirmées"),
    (re.compile(r"\betre\b", re.IGNORECASE), "être"),
    (re.compile(r"\bdecision\b", re.IGNORECASE), "décision"),
    (re.compile(r"\bcloture\b", re.IGNORECASE), "clôture"),
    (re.compile(r"\bfinances\b", re.IGNORECASE), "financés"),
]


def _fix_text(value: str | None) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    text = value
    for pattern, replacement in REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text, text != value


def _fix_json(value: Any) -> tuple[Any, bool]:
    if isinstance(value, str):
        return _fix_text(value)
    if isinstance(value, list):
        changed = False
        items = []
        for item in value:
            fixed, item_changed = _fix_json(item)
            items.append(fixed)
            changed = changed or item_changed
        return items, changed
    if isinstance(value, dict):
        changed = False
        data = {}
        for key, item in value.items():
            fixed, item_changed = _fix_json(item)
            data[key] = fixed
            changed = changed or item_changed
        return data, changed
    return value, False


async def run() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    changed: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).where(Device.id.in_(TARGET_IDS)))).scalars().all()
        for device in devices:
            changed_fields: list[str] = []
            for field in TEXT_FIELDS:
                fixed, did_change = _fix_text(getattr(device, field))
                if did_change:
                    setattr(device, field, fixed)
                    changed_fields.append(field)
            for field in JSON_FIELDS:
                fixed, did_change = _fix_json(getattr(device, field))
                if did_change:
                    setattr(device, field, fixed)
                    changed_fields.append(field)

            if changed_fields:
                tags = list(device.tags or [])
                if "audit:accent_residual_fixed" not in tags:
                    tags.append("audit:accent_residual_fixed")
                device.tags = tags[:24]
                device.updated_at = now
                changed.append(
                    {
                        "id": str(device.id),
                        "title": device.title,
                        "fields": sorted(set(changed_fields)),
                    }
                )

        await db.commit()

    return {"changed": len(changed), "items": changed}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
