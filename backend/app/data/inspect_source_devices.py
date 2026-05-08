"""
Inspecte les fiches rattachees a une source.

Usage:
    docker exec finveille-backend python -m app.data.inspect_source_devices "Nom de source"
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


async def run(source_name: str) -> None:
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(select(Source).where(Source.name == source_name))
        ).scalar_one_or_none()

        if not source:
            print(f"[NOT_FOUND] {source_name}")
            return

        devices = (
            await db.execute(
                select(Device)
                .where(Device.source_id == source.id)
                .order_by(Device.created_at.desc())
            )
        ).scalars().all()

        print(f"source_id={source.id}")
        print(f"source_name={source.name}")
        print(f"device_count={len(devices)}")
        for device in devices[:10]:
            print(
                " | ".join(
                    [
                        str(device.id),
                        device.title or "",
                        device.status or "",
                        device.validation_status or "",
                        device.source_url or "",
                    ]
                )
            )


if __name__ == "__main__":
    source_name = " ".join(sys.argv[1:]).strip()
    if not source_name:
        print("Usage: python -m app.data.inspect_source_devices \"Nom de source\"")
        raise SystemExit(1)
    asyncio.run(run(source_name))
