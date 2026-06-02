"""Audite le lot Afrique round26 avant validation utilisateur."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy import select

from app.data.add_actionable_africa_round26 import DEVICES
from app.database import AsyncSessionLocal
from app.models.device import Device


MOJIBAKE_MARKERS = ("Ã", "Â", "â€™", "â€œ", "â€", "Å“")
WEAK_CONFIRMATION_MARKERS = (
    "doit être confirmé",
    "doivent être confirmés",
    "à confirmer",
    "à vérifier",
)


def _field_text(device: Device) -> str:
    values: list[Any] = [
        device.title,
        device.short_description,
        device.full_description,
        device.eligibility_criteria,
        device.specific_conditions,
        device.required_documents,
        device.funding_details,
        device.recurrence_notes,
        device.source_raw,
        device.tags,
    ]
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            parts.append(value)
        else:
            parts.append(json.dumps(value, ensure_ascii=False, default=str))
    return "\n".join(parts)


def _quality_flags(device: Device, today: date) -> list[str]:
    text = _field_text(device)
    normalized = text.lower()
    flags: list[str] = []

    if any(marker in text for marker in MOJIBAKE_MARKERS):
        flags.append("accent_encoding_issue")
    if not device.source_url or len(device.source_url) < 12:
        flags.append("missing_source_url")
    if device.validation_status != "auto_published":
        flags.append("not_auto_published")
    if device.user_quality_decision not in {"publish", "publish_with_caution"}:
        flags.append("not_publishable_decision")
    if not device.short_description or len(device.short_description) < 120:
        flags.append("weak_short_description")
    if not device.full_description or len(device.full_description) < 450:
        flags.append("weak_full_description")
    if not device.eligibility_criteria or len(device.eligibility_criteria) < 120:
        flags.append("weak_eligibility")
    if not device.funding_details or len(device.funding_details) < 120:
        flags.append("weak_funding_details")
    if not device.specific_conditions or len(device.specific_conditions) < 80:
        flags.append("weak_procedure_or_checks")
    if device.status == "open" and not device.close_date:
        flags.append("open_without_close_date")
    if device.status == "open" and device.close_date and device.close_date < today:
        flags.append("open_with_past_close_date")
    if device.status == "recurring" and device.close_date:
        flags.append("recurring_with_close_date")
    if device.status == "open" and device.is_recurring:
        flags.append("open_marked_recurring")
    if device.status == "recurring" and not device.is_recurring:
        flags.append("recurring_not_marked_recurring")
    if sum(1 for marker in WEAK_CONFIRMATION_MARKERS if marker in normalized) > 3:
        flags.append("too_many_uncertainty_markers")
    if device.country in {"Togo", "Cameroun"} and "RDC" in text:
        flags.append("country_leak_rdc")
    if device.country == "République démocratique du Congo" and any(
        country in text for country in ("Togo", "Cameroun")
    ):
        flags.append("country_leak_other")

    return flags


async def run() -> dict[str, Any]:
    titles = [str(device["title"]) for device in DEVICES]
    today = date.today()

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(select(Device).where(Device.title.in_(titles)).order_by(Device.country, Device.title))
        ).scalars().all()

    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for device in devices:
        flags = _quality_flags(device, today)
        counts.update(flags)
        rows.append(
            {
                "title": device.title,
                "country": device.country,
                "status": device.status,
                "close_date": str(device.close_date) if device.close_date else None,
                "type": device.device_type,
                "quality_score": device.user_quality_score,
                "quality_decision": device.user_quality_decision,
                "validation_status": device.validation_status,
                "flags": flags,
            }
        )

    return {
        "expected": len(titles),
        "matched": len(rows),
        "premium_ready": sum(1 for row in rows if not row["flags"]),
        "needs_review": sum(1 for row in rows if row["flags"]),
        "flag_counts": dict(counts),
        "items": rows,
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
