from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


async def run(source_name: str) -> dict:
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(select(Source).where(Source.name == source_name))
        ).scalar_one_or_none()
        if not source:
            return {"error": "source_not_found", "source": source_name}

        total = (
            await db.execute(select(func.count(Device.id)).where(Device.source_id == source.id))
        ).scalar_one()
        rows = (
            await db.execute(
                select(
                    Device.title,
                    Device.status,
                    Device.device_type,
                    Device.close_date,
                    Device.validation_status,
                    Device.completeness_score,
                    Device.ai_readiness_score,
                )
                .where(Device.source_id == source.id)
                .order_by(Device.created_at.desc())
                .limit(20)
            )
        ).all()

        return {
            "source_id": str(source.id),
            "name": source.name,
            "active": source.is_active,
            "last_success_at": source.last_success_at.isoformat() if source.last_success_at else None,
            "last_checked_at": source.last_checked_at.isoformat() if source.last_checked_at else None,
            "errors": source.consecutive_errors or 0,
            "total_devices": int(total or 0),
            "sample": [
                {
                    "title": title,
                    "status": status,
                    "type": device_type,
                    "close_date": close_date.isoformat() if close_date else None,
                    "validation": validation_status,
                    "completeness": completeness_score,
                    "ai_readiness": ai_readiness_score,
                }
                for (
                    title,
                    status,
                    device_type,
                    close_date,
                    validation_status,
                    completeness_score,
                    ai_readiness_score,
                ) in rows
            ],
        }


def main() -> None:
    source_name = " ".join(sys.argv[1:]).strip()
    if not source_name:
        raise SystemExit('Usage: python -m app.data.inspect_source_devices "Nom de source"')
    print(json.dumps(asyncio.run(run(source_name)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
