from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


TITLES = [
    "AECF - entrepreneuriat feminin pour une economie plus verte au Benin et au Burkina Faso",
    "CORAF - veille innovations agricoles et Prix Abdoulaye Toure",
    "FAIJ Burkina Faso - financement de micro-projets jeunes",
    "FASI Burkina Faso - financement de microprojets du secteur informel",
    "I&P - financement et accompagnement des PME africaines",
]


def _clip(value: str | None, limit: int = 900) -> str | None:
    if not value:
        return None
    text = " ".join(value.split())
    return text[:limit]


async def run() -> list[dict]:
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).where(Device.title.in_(TITLES)).order_by(Device.title.asc()))).scalars().all()
        return [
            {
                "id": str(device.id),
                "title": device.title,
                "organism": device.organism,
                "country": device.country,
                "type": device.device_type,
                "status": device.status,
                "validation_status": device.validation_status,
                "close_date": device.close_date.isoformat() if device.close_date else None,
                "source_url": device.source_url,
                "recurrence_notes": _clip(device.recurrence_notes),
                "short_description": _clip(device.short_description),
                "eligibility_criteria": _clip(device.eligibility_criteria),
                "funding_details": _clip(device.funding_details),
                "source_raw": _clip(device.source_raw, 1200),
                "sections": device.content_sections_json,
            }
            for device in devices
        ]


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
