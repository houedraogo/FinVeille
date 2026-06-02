"""Corrige des accents manquants dans les fiches visibles."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
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

REPLACEMENTS = [
    (re.compile(r"\ba verifier\b", re.IGNORECASE), "à vérifier"),
    (re.compile(r"\ba confirmer\b", re.IGNORECASE), "à confirmer"),
    (re.compile(r"\ba preparer\b", re.IGNORECASE), "à préparer"),
    (re.compile(r"\ba deposer\b", re.IGNORECASE), "à déposer"),
    (re.compile(r"\ba utiliser\b", re.IGNORECASE), "à utiliser"),
    (re.compile(r"\ba prioriser\b", re.IGNORECASE), "à prioriser"),
    (re.compile(r"\ba jour\b", re.IGNORECASE), "à jour"),
    (re.compile(r"\ba l(['’])", re.IGNORECASE), r"à l\1"),
    (re.compile(r"\bA l(['’])"), r"À l\1"),
    (re.compile(r"\ba la\b", re.IGNORECASE), "à la"),
    (re.compile(r"\bA la\b"), "À la"),
]


def _visible(device: Device) -> bool:
    return (
        device.validation_status in VISIBLE_VALIDATION_STATUSES
        and device.user_quality_decision in VISIBLE_USER_DECISIONS
        and device.status in ACTIONABLE_STATUSES
        and device.device_type not in NON_ACTIONABLE_TYPES
    )


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
            new_item, item_changed = _fix_json(item)
            changed = changed or item_changed
            items.append(new_item)
        return items, changed
    if isinstance(value, dict):
        changed = False
        data = {}
        for key, item in value.items():
            new_item, item_changed = _fix_json(item)
            changed = changed or item_changed
            data[key] = new_item
        return data, changed
    return value, False


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    changed_items: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device))).scalars().all()

        for device in devices:
            if not _visible(device):
                continue
            changed_fields: list[str] = []
            for field in TEXT_FIELDS:
                value = getattr(device, field)
                fixed, changed = _fix_text(value)
                if changed:
                    setattr(device, field, fixed)
                    changed_fields.append(field)
            for field in JSON_FIELDS:
                value = getattr(device, field)
                fixed, changed = _fix_json(value)
                if changed:
                    setattr(device, field, fixed)
                    changed_fields.append(field)

            if changed_fields:
                device.updated_at = now
                changed_items.append(
                    {
                        "id": str(device.id),
                        "title": device.title,
                        "fields": sorted(set(changed_fields)),
                    }
                )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "changed": len(changed_items), "items": changed_items[:120]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Corrige les accents manquants dans les fiches visibles.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
