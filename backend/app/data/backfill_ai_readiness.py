"""
Recalcule le score IA-ready de toutes les fiches existantes.

Usage:
    docker exec kafundo-backend python -m app.data.backfill_ai_readiness
    docker exec kafundo-backend python -m app.data.backfill_ai_readiness --apply
"""
import argparse
import asyncio
import json
from collections import Counter
from typing import Any

from sqlalchemy import select, text

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.ai_readiness import compute_ai_readiness


def _device_to_dict(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


async def ensure_columns() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS ai_readiness_score SMALLINT NOT NULL DEFAULT 0"))
        await db.execute(text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS ai_readiness_label VARCHAR(80) NULL"))
        await db.execute(text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS ai_readiness_reasons TEXT[] NULL"))
        await db.execute(text("CREATE INDEX IF NOT EXISTS ix_devices_ai_readiness_label ON devices (ai_readiness_label)"))
        await db.commit()


async def run(*, apply: bool = False, limit: int | None = None) -> dict[str, Any]:
    await ensure_columns()

    async with AsyncSessionLocal() as db:
        query = (
            select(Device, Source)
            .outerjoin(Source, Source.id == Device.source_id)
            .order_by(Device.updated_at.desc().nullslast())
        )
        if limit:
            query = query.limit(limit)
        rows = (await db.execute(query)).all()

        labels: Counter[str] = Counter()
        updated = 0
        preview = []

        for device, source in rows:
            readiness = compute_ai_readiness(_device_to_dict(device), source)
            labels[readiness.label] += 1

            changed = (
                device.ai_readiness_score != readiness.score
                or device.ai_readiness_label != readiness.label
                or list(device.ai_readiness_reasons or []) != readiness.reasons
            )
            if not changed:
                continue

            updated += 1
            if len(preview) < 10:
                preview.append(
                    {
                        "title": device.title,
                        "source": source.name if source else device.organism,
                        "before": {
                            "score": device.ai_readiness_score,
                            "label": device.ai_readiness_label,
                        },
                        "after": {
                            "score": readiness.score,
                            "label": readiness.label,
                            "reasons": readiness.reasons[:6],
                        },
                    }
                )

            if apply:
                device.ai_readiness_score = readiness.score
                device.ai_readiness_label = readiness.label
                device.ai_readiness_reasons = readiness.reasons

        if apply:
            await db.commit()
        else:
            await db.rollback()

        return {
            "dry_run": not apply,
            "scanned": len(rows),
            "updated": updated,
            "labels": dict(labels),
            "preview": preview,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill IA-ready des fiches dispositifs.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
