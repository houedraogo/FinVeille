from __future__ import annotations

import asyncio
import json
from collections import Counter

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.schemas.device import DeviceSearchParams
from app.services.device_service import DeviceService


TARGET_COUNTRIES = [
    "Burkina Faso",
    "Benin",
    "Bénin",
    "Cote d'Ivoire",
    "Côte d'Ivoire",
    "Afrique de l'Ouest",
]


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        service = DeviceService(db)
        result = await service.search(
            DeviceSearchParams(
                countries=TARGET_COUNTRIES,
                sort_by="relevance",
                sort_desc=True,
                page=1,
                page_size=250,
            )
        )
        ids = [device.id for device in result["items"]]
        rows = []
        if ids:
            rows = (
                await db.execute(
                    select(Device, Source)
                    .outerjoin(Source, Source.id == Device.source_id)
                    .where(Device.id.in_(ids))
                )
            ).all()

    by_country = Counter(device.country or "Non renseigne" for device, _ in rows)
    by_type = Counter(device.device_type or "Non renseigne" for device, _ in rows)
    by_status = Counter(device.status or "Non renseigne" for device, _ in rows)
    by_source = Counter((source.name if source else device.organism) or "Sans source" for device, source in rows)
    samples = [
        {
            "title": device.title,
            "country": device.country,
            "type": device.device_type,
            "status": device.status,
            "source": source.name if source else device.organism,
        }
        for device, source in rows[:25]
    ]
    return {
        "visible_target_total": result["total"],
        "returned": len(rows),
        "by_country": dict(by_country),
        "by_type": dict(by_type),
        "by_status": dict(by_status),
        "top_sources": dict(by_source.most_common(15)),
        "samples": samples,
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
