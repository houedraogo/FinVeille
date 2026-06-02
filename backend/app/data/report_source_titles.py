from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


async def main(pattern: str) -> None:
    needle = f"%{pattern}%"
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(
                Device.title,
                Device.country,
                Device.status,
                Device.validation_status,
                Device.user_quality_decision,
                Device.source_url,
                Source.name,
            )
            .join(Source, Source.id == Device.source_id, isouter=True)
            .where(or_(Device.title.ilike(needle), Source.name.ilike(needle), Device.organism.ilike(needle)))
            .order_by(Device.updated_at.desc())
        )
        for row in rows.all():
            print(
                {
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
    parser = argparse.ArgumentParser()
    parser.add_argument("pattern")
    args = parser.parse_args()
    asyncio.run(main(args.pattern))
