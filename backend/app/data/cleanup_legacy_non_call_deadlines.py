"""Retire les fausses deadlines des anciennes fiches non ouvertes."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, not_, or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.data.polish_added_africa_devices import TARGET_DEVICES


NON_CLASSIC_NOTE = (
    "Cette fiche ne correspond pas à un appel ouvert avec date limite unique. "
    "La date de candidature doit être confirmée sur la source officielle."
)


def _deadline_tag_for(device: Device) -> str:
    source = (device.source_url or "").lower()
    if "projects.worldbank.org" in source:
        return "deadline:institutional_project"
    if device.status == "recurring" or device.is_recurring:
        return "deadline:permanent"
    return "deadline:not_communicated"


def _replace_deadline_tag(tags: list[str] | None, next_tag: str) -> list[str]:
    values = {tag for tag in (tags or []) if not tag.startswith("deadline:")}
    values.add(next_tag)
    return sorted(values)


async def run(*, apply: bool = False) -> dict[str, Any]:
    recent_titles = [str(device["title"]) for device in TARGET_DEVICES]
    recent_urls = [str(device["source_url"]) for device in TARGET_DEVICES]
    now = datetime.now(timezone.utc)
    changed: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .where(
                    and_(
                        Device.validation_status != "rejected",
                        Device.close_date.is_not(None),
                        or_(Device.status.in_(["standby", "recurring"]), Device.is_recurring.is_(True)),
                        not_(or_(Device.title.in_(recent_titles), Device.source_url.in_(recent_urls))),
                    )
                )
                .order_by(Device.close_date.asc(), Device.title.asc())
            )
        ).scalars().all()

        for device in devices:
            old_close = device.close_date
            next_tag = _deadline_tag_for(device)
            before = {
                "status": device.status,
                "close_date": str(old_close) if old_close else None,
                "tags": [tag for tag in (device.tags or []) if tag.startswith("deadline:")],
            }
            device.close_date = None
            device.tags = _replace_deadline_tag(device.tags, next_tag)
            device.recurrence_notes = device.recurrence_notes or NON_CLASSIC_NOTE
            if device.user_quality_decision == "publish":
                device.user_quality_decision = "publish_with_caution"
            reasons = set(device.user_quality_reasons or [])
            reasons.add("date_a_confirmer")
            device.user_quality_reasons = sorted(reasons)
            device.updated_at = now
            changed.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "source_url": device.source_url,
                    "before": before,
                    "after": {
                        "status": device.status,
                        "close_date": None,
                        "tags": [tag for tag in device.tags if tag.startswith("deadline:")],
                    },
                }
            )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "matched": len(devices), "changed": changed[:120]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean legacy close dates that are not application deadlines.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
