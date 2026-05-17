from __future__ import annotations

import asyncio
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.data.audit_english_titles import (
    PUBLIC_VALIDATION_STATUSES,
    is_africa_related,
    looks_english_title,
)
from app.database import AsyncSessionLocal
from app.models.device import Device


def _source_name(device: Device) -> str:
    return device.source.name if device.source else "Import manuel / historique"


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.validation_status.in_(PUBLIC_VALIDATION_STATUSES))
                .order_by(Device.source_id.asc(), Device.title.asc())
            )
        ).scalars().all()

        rows = []
        for device in devices:
            if not looks_english_title(device.title):
                continue
            rows.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "source": _source_name(device),
                    "country": device.country,
                    "status": device.status,
                    "device_type": device.device_type,
                    "close_date": device.close_date.isoformat() if device.close_date else None,
                    "validation_status": device.validation_status,
                    "africa_related": is_africa_related(device),
                    "source_url": device.source_url,
                }
            )

        return {
            "audit_date": date.today().isoformat(),
            "count": len(rows),
            "rows": rows,
        }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
