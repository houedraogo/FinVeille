"""Corrige les liens visibles restes en retry_or_review apres audit global."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import compute_completeness, normalize_title


URL_FIXES: dict[str, dict[str, Any]] = {
    "db2832bd-b130-4c48-8b03-2599261aae47": {
        "source_url": "https://startupandgo-auvergnerhonealpes.fr/soutien-financier-emergence/",
        "source_raw": "Page officielle Start-up & Go Auvergne-Rhône-Alpes sur le soutien financier à l'émergence.",
    },
    "237e4e16-a489-4f58-9bbe-e0637672780f": {
        "source_url": "https://sofinnovapartners.com/",
        "source_raw": "Site officiel Sofinnova Partners.",
    },
    "3a121d74-31dd-4832-87fc-d7b53b710b41": {
        "source_url": "https://home.angelsquare.co/",
        "source_raw": "Site officiel Angelsquare.",
    },
    "a40694a7-322a-4181-8907-2859d086aa12": {
        "source_url": "https://www.ventechvc.com/",
        "source_raw": "Site officiel Ventech.",
    },
    "67af3bbc-46e5-4002-96e2-94f5cdccab1e": {
        "source_url": "https://partechpartners.com/",
        "source_raw": "Site officiel Partech.",
    },
    "f49a58a5-b586-4765-af08-078e7b7bd667": {
        "source_raw": "Page officielle URSSAF sur la franchise de cotisations pour les stages en milieu professionnel.",
    },
}


def _append_tags(device: Device, *tags: str) -> None:
    current = list(device.tags or [])
    for tag in tags:
        if tag not in current:
            current.append(tag)
    device.tags = current[:24]


def _refresh(device: Device) -> None:
    payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
    device.completeness_score = compute_completeness(payload)
    device.title_normalized = normalize_title(device.title)
    now = datetime.now(timezone.utc)
    device.last_verified_at = now
    device.updated_at = now


async def run() -> dict[str, Any]:
    result: dict[str, Any] = {"fixed": []}
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).where(Device.id.in_(set(URL_FIXES))))).scalars().all()
        for device in devices:
            device_id = str(device.id)
            for field, value in URL_FIXES[device_id].items():
                setattr(device, field, value)
            _append_tags(device, "audit:retry_link_fixed", "source:verified_20260601")
            _refresh(device)
            result["fixed"].append({"id": device_id, "title": device.title, "source_url": device.source_url})

        await db.commit()

    return result


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
