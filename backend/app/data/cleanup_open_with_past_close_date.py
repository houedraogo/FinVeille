import asyncio
from datetime import date

from sqlalchemy import and_, select

from app.database import AsyncSessionLocal
from app.models.device import Device


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .where(
                    and_(
                        Device.status == "open",
                        Device.close_date.is_not(None),
                        Device.close_date < date.today(),
                    )
                )
                .order_by(Device.close_date.asc(), Device.title.asc())
            )
        ).scalars().all()

        updated = 0
        preview: list[dict] = []

        for device in devices:
            if device.status != "expired":
                device.status = "expired"
                updated += 1
                preview.append(
                    {
                        "title": device.title,
                        "close_date": str(device.close_date),
                        "validation_status": device.validation_status,
                        "new_status": device.status,
                    }
                )

        await db.commit()
        return {"updated": updated, "preview": preview}


def main() -> None:
    import json

    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
