from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


PDF_DUPLICATE_URL = "https://www.bceao.int/sites/default/files/2025-10/Affiche-PAF-2026-NouvelleVersion.pdf"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Device).where(Device.source_url == PDF_DUPLICATE_URL))
        hidden = 0
        for device in result.scalars().all():
            device.validation_status = "admin_only"
            device.user_quality_decision = "admin_only"
            tags = set(device.tags or [])
            tags.update({"visibility:admin_only", "dedupe:hidden_duplicate", "source:bceao_pdf_duplicate"})
            device.tags = sorted(tags)
            device.updated_at = datetime.now(timezone.utc)
            hidden += 1

        await db.commit()
        print({"hidden_bceao_pdf_duplicates": hidden})


if __name__ == "__main__":
    asyncio.run(main())
