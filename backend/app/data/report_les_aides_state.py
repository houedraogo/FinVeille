from __future__ import annotations

import asyncio
import json

from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


SOURCE_NAME = "les-aides.fr - solutions de financement entreprises"
PUBLIC_STATUSES = {"auto_published", "validated"}


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one()

        distribution_rows = (
            await db.execute(
                select(Device.validation_status, Device.status, func.count(Device.id))
                .where(Device.source_id == source.id)
                .group_by(Device.validation_status, Device.status)
                .order_by(Device.validation_status.asc(), Device.status.asc())
            )
        ).all()

        public_without_date_rows = (
            await db.execute(
                select(Device.title, Device.status, Device.validation_status, Device.recurrence_notes)
                .where(
                    Device.source_id == source.id,
                    Device.validation_status.in_(PUBLIC_STATUSES),
                    Device.close_date.is_(None),
                )
                .order_by(Device.status.asc(), Device.title.asc())
                .limit(30)
            )
        ).all()

        public_counts_rows = (
            await db.execute(
                select(Device.status, func.count(Device.id))
                .where(Device.source_id == source.id, Device.validation_status.in_(PUBLIC_STATUSES))
                .group_by(Device.status)
                .order_by(Device.status.asc())
            )
        ).all()

    return {
        "source": SOURCE_NAME,
        "distribution": [
            {"validation_status": validation, "status": status, "count": count}
            for validation, status, count in distribution_rows
        ],
        "public_counts": [{"status": status, "count": count} for status, count in public_counts_rows],
        "public_without_date_sample": [
            {
                "title": title,
                "status": status,
                "validation_status": validation,
                "recurrence_notes": notes,
            }
            for title, status, validation, notes in public_without_date_rows
        ],
        "public_without_date_sample_count": len(public_without_date_rows),
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
