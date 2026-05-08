import asyncio
import json

from sqlalchemy import func, or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


async def run() -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Source.name, Device.title, Device.validation_status, Device.short_description)
                .join(Source, Source.id == Device.source_id)
                .where(
                    or_(
                        Device.organism.ilike("%World Bank%"),
                        Source.organism.ilike("%World Bank%"),
                        Source.name.ilike("%Banque Mondiale%"),
                    ),
                    or_(
                        Device.short_description.is_(None),
                        func.length(func.trim(func.coalesce(Device.short_description, ""))) < 120,
                    ),
                )
                .order_by(Source.name.asc(), Device.title.asc())
            )
        ).all()

        return [
            {
                "source": source,
                "title": title,
                "validation_status": validation_status,
                "short_description": (short_description or "")[:180],
            }
            for source, title, validation_status, short_description in rows
        ]


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
