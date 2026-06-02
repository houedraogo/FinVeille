"""Corrige les echeances manifestement incoherentes sans recalcul global."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.data.polish_added_africa_devices import TARGET_DEVICES


UNKNOWN_DEADLINE_NOTE = (
    "Date limite non communiquée par la source officielle : vérifier la page source avant de prioriser."
)


def _deadline_tags(tags: list[str] | None) -> set[str]:
    return {tag for tag in (tags or []) if tag.startswith("deadline:")}


def _replace_deadline_tag(tags: list[str] | None, next_tag: str) -> list[str]:
    values = {tag for tag in (tags or []) if not tag.startswith("deadline:")}
    values.add(next_tag)
    return sorted(values)


async def _target_added_open_without_close(db) -> list[Device]:
    titles = [str(device["title"]) for device in TARGET_DEVICES]
    urls = [str(device["source_url"]) for device in TARGET_DEVICES]
    return (
        await db.execute(
            select(Device).where(
                and_(
                    or_(Device.title.in_(titles), Device.source_url.in_(urls)),
                    Device.status == "open",
                    Device.close_date.is_(None),
                    Device.is_recurring.is_(False),
                )
            )
        )
    ).scalars().all()


async def run(*, apply: bool = False) -> dict[str, Any]:
    today = date.today()
    now = datetime.now(timezone.utc)
    changed: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        past_open = (
            await db.execute(
                select(Device)
                .where(
                    and_(
                        Device.status == "open",
                        Device.close_date.is_not(None),
                        Device.close_date < today,
                        Device.validation_status != "rejected",
                    )
                )
                .order_by(Device.close_date.asc(), Device.title.asc())
            )
        ).scalars().all()
        added_open_without_close = await _target_added_open_without_close(db)

        for device in past_open:
            before = {
                "status": device.status,
                "close_date": str(device.close_date) if device.close_date else None,
                "tags": sorted(_deadline_tags(device.tags)),
            }
            device.status = "expired"
            device.is_recurring = False
            device.tags = _replace_deadline_tag(device.tags, "deadline:expired")
            device.updated_at = now
            changed.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "reason": "open_with_past_close_date",
                    "before": before,
                    "after": {
                        "status": device.status,
                        "close_date": str(device.close_date) if device.close_date else None,
                        "tags": sorted(_deadline_tags(device.tags)),
                    },
                }
            )

        for device in added_open_without_close:
            before = {
                "status": device.status,
                "close_date": None,
                "tags": sorted(_deadline_tags(device.tags)),
            }
            device.status = "standby"
            device.is_recurring = False
            device.validation_status = "pending_review"
            device.recurrence_notes = device.recurrence_notes or UNKNOWN_DEADLINE_NOTE
            device.tags = _replace_deadline_tag(device.tags, "deadline:not_communicated")
            device.user_quality_decision = "publish_with_caution"
            reasons = set(device.user_quality_reasons or [])
            reasons.add("date_a_confirmer")
            device.user_quality_reasons = sorted(reasons)
            device.updated_at = now
            changed.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "reason": "added_open_without_close_date",
                    "before": before,
                    "after": {
                        "status": device.status,
                        "close_date": None,
                        "tags": sorted(_deadline_tags(device.tags)),
                    },
                }
            )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {
        "dry_run": not apply,
        "past_open_fixed": len(past_open),
        "added_open_without_close_fixed": len(added_open_without_close),
        "changed": changed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix obvious deadline mismatches.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
