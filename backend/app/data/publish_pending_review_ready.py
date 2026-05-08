from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.data.audit_decision_quality import _decision_level, _issues_for
from app.database import AsyncSessionLocal
from app.models.device import Device


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device).where(Device.validation_status == "pending_review")
            )
        ).scalars().all()

        updated = 0
        kept = 0
        preview: list[dict] = []

        for device in devices:
            issues = _issues_for(device)
            level = _decision_level(issues)
            if level == "pret_decision":
                device.validation_status = "auto_published"
                updated += 1
                preview.append(
                    {
                        "id": str(device.id),
                        "title": device.title,
                        "status": device.status,
                        "decision_level": level,
                    }
                )
            else:
                kept += 1

        await db.commit()

    return {"scanned": len(devices), "published": updated, "kept_pending": kept, "preview": preview}


def main() -> None:
    import json

    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
