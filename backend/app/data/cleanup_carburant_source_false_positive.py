"""Nettoie le faux positif dead_link sur l'aide carburant grands rouleurs."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


DEVICE_ID = UUID("a6d02f0f-5fdf-411c-8aae-560650b57dca")
OFFICIAL_URL = "https://www.impots.gouv.fr/simulateur-aide-carburant-grands-rouleurs"


async def run() -> dict:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        device = await db.get(Device, DEVICE_ID)
        if not device:
            return {"updated": False, "reason": "device_not_found"}

        source = None
        if device.source_id:
            source = await db.get(Source, device.source_id)
        if not source:
            source = (
                await db.execute(select(Source).where(Source.name == "impots.gouv.fr - aide carburant grands rouleurs"))
            ).scalar_one_or_none()

        device.source_url = OFFICIAL_URL
        device.source_raw = (
            "Source officielle impots.gouv.fr active : simulateur d'indemnité carburant 2026 pour les travailleurs grands rouleurs."
        )
        tags = list(device.tags or [])
        for tag in ("audit:dead_link_false_positive", "source:verified_impots_20260601"):
            if tag not in tags:
                tags.append(tag)
        device.tags = tags[:24]
        device.last_verified_at = now
        device.updated_at = now

        source_payload = None
        if source:
            source.url = OFFICIAL_URL
            source.is_active = True
            source.consecutive_errors = 0
            source.last_checked_at = now
            source.last_success_at = now
            source.notes = (
                "Source officielle vérifiée le 2026-06-01. Le simulateur impots.gouv.fr est actif ; "
                "ancien signal dead_link conservé comme faux positif."
            )
            source.updated_at = now
            source_payload = {"id": str(source.id), "name": source.name, "consecutive_errors": source.consecutive_errors}

        await db.commit()

    return {
        "updated": True,
        "device": {"id": str(DEVICE_ID), "title": device.title, "source_url": device.source_url},
        "source": source_payload,
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
