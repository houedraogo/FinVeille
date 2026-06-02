"""Restaure les cles techniques des sections visibles."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


VISIBLE_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
VISIBLE_USER_DECISIONS = {None, "publish", "publish_with_caution"}
ACTIONABLE_STATUSES = {"open", "recurring"}
NON_ACTIONABLE_TYPES = {"autre", "institutional_project"}
SECTION_FIELDS = ["content_sections_json", "ai_rewritten_sections_json"]

KEY_MAP = {
    "présentation": "presentation",
    "demarche": "procedure",
    "démarche": "procedure",
    "critères": "eligibility",
    "éligibilité": "eligibility",
    "montant": "funding",
    "calendrier": "calendar",
}


def _visible(device: Device) -> bool:
    return (
        device.validation_status in VISIBLE_VALIDATION_STATUSES
        and device.user_quality_decision in VISIBLE_USER_DECISIONS
        and device.status in ACTIONABLE_STATUSES
        and device.device_type not in NON_ACTIONABLE_TYPES
    )


def _fix_sections(value: Any) -> tuple[Any, bool]:
    if not isinstance(value, list):
        return value, False
    changed = False
    sections: list[Any] = []
    for item in value:
        if not isinstance(item, dict):
            sections.append(item)
            continue
        section = dict(item)
        key = section.get("key")
        if isinstance(key, str):
            normalized = KEY_MAP.get(key.strip().lower())
            if normalized and normalized != key:
                section["key"] = normalized
                changed = True
        sections.append(section)
    return sections, changed


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    changed_items: list[dict[str, Any]] = []
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device))).scalars().all()
        for device in devices:
            if not _visible(device):
                continue
            fields: list[str] = []
            for field in SECTION_FIELDS:
                fixed, changed = _fix_sections(getattr(device, field))
                if changed:
                    setattr(device, field, fixed)
                    fields.append(field)
            if fields:
                device.updated_at = now
                changed_items.append({"id": str(device.id), "title": device.title, "fields": fields})
        if apply:
            await db.commit()
        else:
            await db.rollback()
    return {"dry_run": not apply, "changed": len(changed_items), "items": changed_items[:120]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaure les cles techniques des sections visibles.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
