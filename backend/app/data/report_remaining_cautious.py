from __future__ import annotations

import asyncio
import json

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.data.audit_decision_quality import _decision_level, _issues_for
from app.database import AsyncSessionLocal
from app.models.device import Device


async def run() -> list[dict]:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.validation_status != "rejected")
            )
        ).scalars().all()

        rows: list[dict] = []
        for device in devices:
            issues = _issues_for(device)
            level = _decision_level(issues)
            if level == "pret_decision":
                continue
            rows.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "source": device.source.name if device.source else None,
                    "status": device.status,
                    "device_type": device.device_type,
                    "decision_level": level,
                    "issues": issues,
                    "recurrence_notes": device.recurrence_notes,
                    "short_description": (device.short_description or "")[:320],
                }
            )
        return rows


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
