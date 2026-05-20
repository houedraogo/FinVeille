import asyncio
from collections import Counter

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.services.user_quality import compute_user_quality


async def main() -> None:
    counts: Counter[str] = Counter()
    updated = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Device))
        devices = result.scalars().all()
        for device in devices:
            payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            quality = compute_user_quality(payload)
            counts[quality.decision] += 1
            if (
                device.user_quality_score != quality.score
                or device.user_quality_decision != quality.decision
                or device.user_quality_reasons != quality.reasons
            ):
                device.user_quality_score = quality.score
                device.user_quality_decision = quality.decision
                device.user_quality_reasons = quality.reasons
                updated += 1
        await db.commit()

    print(f"updated={updated}")
    for decision, count in sorted(counts.items()):
        print(f"{decision}={count}")


if __name__ == "__main__":
    asyncio.run(main())
