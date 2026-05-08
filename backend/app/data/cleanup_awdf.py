"""
Nettoie et publie la fiche AWDF issue de la collecte.

Usage:
    docker exec finveille-backend python -m app.data.cleanup_awdf
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


async def run() -> None:
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(
                select(Source).where(Source.name == "AWDF - grants and resourcing")
            )
        ).scalar_one_or_none()
        if not source:
            print("[NOT_FOUND] source")
            return

        devices = (
            await db.execute(select(Device).where(Device.source_id == source.id))
        ).scalars().all()
        if not devices:
            print("[NOT_FOUND] no devices")
            return

        for device in devices:
            device.title = "AWDF - subventions pour organisations de femmes en Afrique"
            device.status = "recurring"
            device.is_recurring = True
            device.validation_status = "auto_published"
            device.recurrence_notes = (
                "Le grantmaking AWDF fonctionne selon des ouvertures recurrentes ou variables, "
                "sans date limite publique unique visible sur cette page de reference."
            )
            device.country = "Afrique"
            device.region = "Afrique"
            device.zone = "Afrique"
            device.geographic_scope = "continental"
            device.device_type = "subvention"
            device.aid_nature = "subvention"

        await db.commit()
        print(f"[OK] {len(devices)} fiche(s) AWDF nettoyee(s)")


if __name__ == "__main__":
    asyncio.run(run())
