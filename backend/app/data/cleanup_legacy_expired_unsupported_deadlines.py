"""Retire les dates expirees impossibles a justifier dans le contenu local."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select

from app.database import AsyncSessionLocal
from app.models.device import Device


NOTE = "Fiche expirée sans date limite exploitable conservée dans le contenu local."


def _replace_deadline_tag(tags: list[str] | None) -> list[str]:
    values = {tag for tag in (tags or []) if not tag.startswith("deadline:")}
    values.add("deadline:expired")
    return sorted(values)


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    changed: list[dict[str, Any]] = []
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device).where(
                    and_(
                        Device.status == "expired",
                        Device.close_date.is_not(None),
                        Device.tags.any("deadline:not_communicated"),
                    )
                )
            )
        ).scalars().all()

        for device in devices:
            before = {
                "close_date": str(device.close_date) if device.close_date else None,
                "tags": [tag for tag in (device.tags or []) if tag.startswith("deadline:")],
            }
            device.close_date = None
            device.tags = _replace_deadline_tag(device.tags)
            device.recurrence_notes = NOTE
            device.updated_at = now
            changed.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "before": before,
                    "after": {
                        "close_date": None,
                        "tags": [tag for tag in (device.tags or []) if tag.startswith("deadline:")],
                    },
                }
            )

        if apply:
            await db.commit()
        else:
            await db.rollback()
    return {"dry_run": not apply, "matched": len(devices), "changed": changed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean unsupported expired deadlines.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
