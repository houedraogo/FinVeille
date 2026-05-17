from __future__ import annotations

import asyncio
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.data.audit_english_titles import PUBLIC_VALIDATION_STATUSES, looks_english_title
from app.database import AsyncSessionLocal
from app.models.device import Device


def _source_name(device: Device) -> str:
    return device.source.name if device.source else "Import manuel / historique"


def _row(device: Device) -> dict:
    return {
        "id": str(device.id),
        "title": device.title,
        "source": _source_name(device),
        "country": device.country,
        "status": device.status,
        "validation_status": device.validation_status,
        "device_type": device.device_type,
        "close_date": device.close_date.isoformat() if device.close_date else None,
        "source_url": device.source_url,
    }


async def run() -> dict:
    today = date.today()
    async with AsyncSessionLocal() as db:
        open_past = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(
                    Device.status == "open",
                    Device.close_date.is_not(None),
                    Device.close_date < today,
                )
                .order_by(Device.close_date.asc())
            )
        ).scalars().all()

        weak_texts = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(
                    (Device.short_description.is_(None))
                    | (Device.short_description.op("~")(r"^\s*$"))
                    | (Device.short_description.op("~")(r"^.{0,119}$")),
                )
                .order_by(Device.updated_at.desc())
            )
        ).scalars().all()

        public_english = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.validation_status.in_(PUBLIC_VALIDATION_STATUSES))
                .order_by(Device.updated_at.desc())
            )
        ).scalars().all()

        public_english_rows = [
            _row(device) for device in public_english if looks_english_title(device.title)
        ]

        return {
            "audit_date": today.isoformat(),
            "open_with_past_close_date": [_row(device) for device in open_past],
            "weak_texts": [_row(device) for device in weak_texts[:25]],
            "public_english_titles": public_english_rows,
        }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
