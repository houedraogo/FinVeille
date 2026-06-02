from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(
                Device.id,
                Device.title,
                Device.country,
                Device.status,
                Device.validation_status,
                Device.user_quality_decision,
                Device.source_url,
                Source.name,
            )
            .join(Source, Source.id == Device.source_id, isouter=True)
            .where((Device.title.ilike("%FADIGA%")) | (Source.name.ilike("%FADIGA%")))
            .order_by(Device.updated_at.desc())
        )
        for row in rows.all():
            print(
                {
                    "id": str(row.id),
                    "title": row.title,
                    "country": row.country,
                    "status": row.status,
                    "validation_status": row.validation_status,
                    "decision": row.user_quality_decision,
                    "source": row.name,
                    "url": row.source_url,
                }
            )


if __name__ == "__main__":
    asyncio.run(main())
