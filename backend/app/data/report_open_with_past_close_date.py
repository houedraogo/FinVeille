import asyncio
import json
from datetime import date

from sqlalchemy import and_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


async def run() -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Device.title, Device.close_date, Device.status, Device.validation_status, Source.name)
                .join(Source, Device.source_id == Source.id, isouter=True)
                .where(
                    and_(
                        Device.status == "open",
                        Device.close_date.is_not(None),
                        Device.close_date < date.today(),
                    )
                )
                .order_by(Device.close_date.asc(), Device.title.asc())
            )
        ).all()

        return [
            {
                "title": title,
                "close_date": str(close_date),
                "status": status,
                "validation_status": validation_status,
                "source": source_name or "Sans source",
            }
            for title, close_date, status, validation_status, source_name in rows
        ]


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
