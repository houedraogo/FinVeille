"""Audite les dates limites des fiches Afrique ajoutees recemment."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any

from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.data.polish_added_africa_devices import TARGET_DEVICES


UNKNOWN_SIGNALS = (
    "date limite non communiqu",
    "sans date limite",
    "aucune date limite",
    "confirmer la date",
    "verifier la date",
    "vérifier la date",
    "a confirmer",
    "à confirmer",
    "a verifier",
    "à vérifier",
)

RECURRENT_SIGNALS = (
    "recurrent",
    "récurrent",
    "guichet",
    "permanent",
    "au fil de l'eau",
    "cohortes",
    "sessions",
    "appels ponctuels",
)


def _text(device: Device) -> str:
    values = [
        device.title,
        device.short_description,
        device.full_description,
        device.eligibility_criteria,
        device.specific_conditions,
        device.funding_details,
        device.recurrence_notes,
        device.source_raw,
    ]
    return " ".join(value or "" for value in values).lower()


async def run() -> dict[str, Any]:
    titles = [str(device["title"]) for device in TARGET_DEVICES]
    urls = [str(device["source_url"]) for device in TARGET_DEVICES]
    today = date.today()
    items: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .where(or_(Device.title.in_(titles), Device.source_url.in_(urls)))
                .order_by(Device.country.asc(), Device.title.asc())
            )
        ).scalars().all()

        for device in devices:
            text = _text(device)
            flags: list[str] = []
            if device.close_date and device.status in {"recurring", "standby"}:
                flags.append("close_date_on_non_deadline_status")
            if device.close_date and device.close_date < today and device.status == "open":
                flags.append("open_with_past_close_date")
            if device.close_date and any(signal in text for signal in UNKNOWN_SIGNALS):
                flags.append("close_date_but_text_says_confirm_or_unknown")
            if device.close_date and any(signal in text for signal in RECURRENT_SIGNALS) and device.is_recurring:
                flags.append("close_date_on_recurring_device")
            if not device.close_date and device.status == "open" and not device.is_recurring:
                flags.append("open_without_close_date")

            items.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "country": device.country,
                    "status": device.status,
                    "is_recurring": device.is_recurring,
                    "close_date": str(device.close_date) if device.close_date else None,
                    "tags": [tag for tag in (device.tags or []) if tag.startswith("deadline:")],
                    "flags": flags,
                }
            )

    flagged = [item for item in items if item["flags"]]
    return {
        "matched": len(items),
        "with_close_date": sum(1 for item in items if item["close_date"]),
        "flagged": len(flagged),
        "items": flagged or items,
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
