from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.data.audit_english_titles import looks_english_title
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


SOURCE_NAME = "Global South Opportunities - Funding"


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(select(Source).where(Source.name == SOURCE_NAME))
        ).scalar_one()
        devices = (
            await db.execute(
                select(Device)
                .where(
                    Device.source_id == source.id,
                    Device.validation_status.in_(["auto_published", "approved", "validated", "pending_review"]),
                )
                .order_by(Device.status.asc(), Device.close_date.asc(), Device.title.asc())
            )
        ).scalars().all()

        rows = [
            {
                "id": str(device.id),
                "title": device.title,
                "status": device.status,
                "validation_status": device.validation_status,
                "close_date": device.close_date.isoformat() if device.close_date else None,
                "device_type": device.device_type,
                "english_title": looks_english_title(device.title),
            }
            for device in devices
            if looks_english_title(device.title) or device.close_date is None
        ]

        return {
            "source": SOURCE_NAME,
            "total": len(devices),
            "to_review": len(rows),
            "rows": rows,
        }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
