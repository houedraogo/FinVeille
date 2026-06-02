"""Audit editorial fin des textes visibles dans les fiches."""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
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

DANGLING_ENDINGS = (
    " de",
    " des",
    " du",
    " d'",
    " l'",
    " la",
    " le",
    " les",
    " un",
    " une",
    " et",
    " ou",
    " pour",
    " avec",
    " sans",
    " dans",
    " aux",
    " au",
    " à",
    " a",
)
PLACEHOLDER_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bà compléter\b",
        r"\ba completer\b",
        r"\btbd\b",
        r"\bvoir source\b",
    ]
]
RAW_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
REPEATED_SPACES_RE = re.compile(r" {2,}")
BROKEN_WORD_RE = re.compile(r"\b\w+-\s+\w+\b")


def _visible(device: Device) -> bool:
    return (
        device.validation_status in VISIBLE_VALIDATION_STATUSES
        and device.user_quality_decision in VISIBLE_USER_DECISIONS
        and device.status in ACTIONABLE_STATUSES
        and device.device_type not in NON_ACTIONABLE_TYPES
    )


def _field_value(device: Device, field: str) -> str:
    return str(getattr(device, field) or "").strip()


def _flags_for_text(field: str, text: str) -> list[str]:
    flags: list[str] = []
    if not text:
        return flags

    lowered = text.lower().rstrip()
    if field != "title" and len(text) > 120 and lowered.endswith(DANGLING_ENDINGS):
        flags.append("dangling_sentence_end")
    if field != "title" and len(text) > 160 and text[-1:] not in ".!?…)\"'»":
        flags.append("missing_terminal_punctuation")
    if any(pattern.search(text) for pattern in PLACEHOLDER_PATTERNS):
        flags.append("placeholder_text")
    if field != "source_url" and RAW_URL_RE.search(text):
        flags.append("raw_url_in_copy")
    if REPEATED_SPACES_RE.search(text):
        flags.append("repeated_spaces")
    if BROKEN_WORD_RE.search(text):
        flags.append("broken_hyphenated_word")
    return flags


async def run() -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).order_by(Device.updated_at.desc().nullslast()))).scalars().all()

    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for device in devices:
        if not _visible(device):
            continue
        field_flags: dict[str, list[str]] = {}
        for field in TEXT_FIELDS:
            flags = _flags_for_text(field, _field_value(device, field))
            if flags:
                field_flags[field] = flags
                counts.update(flags)
        if field_flags:
            rows.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "country": device.country,
                    "status": device.status,
                    "close_date": str(device.close_date) if device.close_date else None,
                    "field_flags": field_flags,
                    "samples": {
                        field: _field_value(device, field)[-220:]
                        for field in field_flags
                    },
                }
            )

    return {
        "visible_with_polish_flags": len(rows),
        "flag_counts": dict(counts),
        "items": rows[:80],
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
