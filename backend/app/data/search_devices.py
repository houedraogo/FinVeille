"""
Recherche simple de fiches par mot-cle dans le titre ou l'organisme.

Usage:
    docker exec finveille-backend python -m app.data.search_devices janngo
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device


async def run(term: str) -> None:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .where(
                    or_(
                        Device.title.ilike(f"%{term}%"),
                        Device.organism.ilike(f"%{term}%"),
                    )
                )
                .order_by(Device.updated_at.desc())
            )
        ).scalars().all()

        print(f"count={len(devices)}")
        for device in devices[:20]:
            print(
                " | ".join(
                    [
                        str(device.id),
                        device.title or "",
                        device.organism or "",
                        str(device.source_id or ""),
                        device.status or "",
                        device.validation_status or "",
                    ]
                )
            )


if __name__ == "__main__":
    term = " ".join(sys.argv[1:]).strip()
    if not term:
        print("Usage: python -m app.data.search_devices <term>")
        raise SystemExit(1)
    asyncio.run(run(term))
