from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


SOURCE_NAME = "les-aides.fr - solutions de financement entreprises"


async def run(apply: bool = False) -> dict:
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one()
        devices = (
            await db.execute(
                select(Device)
                .where(
                    Device.source_id == source.id,
                    Device.validation_status == "auto_published",
                    Device.status == "expired",
                    Device.close_date.is_(None),
                )
                .order_by(Device.title.asc())
            )
        ).scalars().all()

        preview = []
        now = datetime.now(timezone.utc)
        for device in devices:
            preview.append({"title": device.title, "status": device.status})
            if not apply:
                continue

            device.validation_status = "admin_only"
            tags = list(device.tags or [])
            for tag in ("visibility:admin_only", "quality:expired_without_deadline", "source:les_aides"):
                if tag not in tags:
                    tags.append(tag)
            device.tags = sorted(tags)
            analysis = dict(device.decision_analysis or {})
            analysis["public_visibility"] = "admin_only"
            analysis["admin_only_reason"] = (
                "Fiche les-aides.fr expirée sans date de clôture exploitable : conservée en historique admin, masquée côté utilisateur."
            )
            analysis["admin_only_at"] = now.isoformat()
            device.decision_analysis = analysis

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "updated": len(devices) if apply else 0, "matched": len(devices), "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Masque les fiches les-aides.fr expirées sans date fiable.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
