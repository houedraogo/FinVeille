"""Nettoie les incoherences restantes de deadline sur les anciennes fiches."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


VERIFIED_DEADLINES = {
    "https://www.globalsouthopportunities.com/2026/04/21/global-120/": "Date limite confirmée dans la source : 8 juin 2026.",
    "https://www.globalsouthopportunities.com/2026/05/13/agog/": "Date limite confirmée dans la source : 12 juin 2026.",
    "https://www.globalsouthopportunities.com/2026/04/27/award-9/": "Date limite confirmée dans la source : 17 juin 2026.",
    "https://www.common-fund.org/call-for-proposals": "Date limite confirmée par le Common Fund for Commodities : 1 octobre 2026.",
}

UNSUPPORTED_OPEN_DEADLINES = {
    "https://www.energie.gouv.ci/actualite/avis-dappel-a-projets-foname-2026-69c535a39f83a": (
        "La page officielle annonce l'appel, mais la date limite n'est pas visible dans le contenu exploitable."
    )
}


def _replace_deadline_tag(tags: list[str] | None, next_tag: str) -> list[str]:
    values = {tag for tag in (tags or []) if not tag.startswith("deadline:")}
    values.add(next_tag)
    return sorted(values)


def _remove_tag(tags: list[str] | None, tag_to_remove: str) -> list[str]:
    return sorted(tag for tag in (tags or []) if tag != tag_to_remove)


def _has_unknown_deadline_note(device: Device) -> bool:
    text = " ".join(
        value or ""
        for value in (
            device.recurrence_notes,
            device.source_raw,
            device.specific_conditions,
            device.full_description,
        )
    ).lower()
    return (
        "date limite non communiqu" in text
        or "sans date limite" in text
        or "date de candidature doit être confirmée" in text
    )


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    changed: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        urls = set(VERIFIED_DEADLINES) | set(UNSUPPORTED_OPEN_DEADLINES)
        devices = (
            await db.execute(select(Device).where(Device.source_url.in_(urls)))
        ).scalars().all()

        for device in devices:
            before = {
                "status": device.status,
                "close_date": str(device.close_date) if device.close_date else None,
                "tags": [tag for tag in (device.tags or []) if tag.startswith("deadline:")],
                "recurrence_notes": device.recurrence_notes,
            }
            if device.source_url in VERIFIED_DEADLINES and device.close_date:
                device.tags = _remove_tag(device.tags, "deadline:not_communicated")
                if device.status == "expired":
                    device.tags = _replace_deadline_tag(device.tags, "deadline:expired")
                else:
                    device.tags = _replace_deadline_tag(device.tags, "deadline:verified_from_raw")
                if _has_unknown_deadline_note(device):
                    device.recurrence_notes = VERIFIED_DEADLINES[device.source_url]
                reasons = set(device.user_quality_reasons or [])
                reasons.discard("date_a_confirmer")
                reasons.add("date_confirmee")
                device.user_quality_reasons = sorted(reasons)
            elif device.source_url in UNSUPPORTED_OPEN_DEADLINES:
                device.close_date = None
                device.status = "standby"
                device.validation_status = "pending_review"
                device.tags = _replace_deadline_tag(device.tags, "deadline:not_communicated")
                device.recurrence_notes = UNSUPPORTED_OPEN_DEADLINES[device.source_url]
                reasons = set(device.user_quality_reasons or [])
                reasons.add("date_a_confirmer")
                device.user_quality_reasons = sorted(reasons)
                device.user_quality_decision = "publish_with_caution"
            else:
                continue

            device.updated_at = now
            changed.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "source_url": device.source_url,
                    "before": before,
                    "after": {
                        "status": device.status,
                        "close_date": str(device.close_date) if device.close_date else None,
                        "tags": [tag for tag in (device.tags or []) if tag.startswith("deadline:")],
                        "recurrence_notes": device.recurrence_notes,
                    },
                }
            )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "changed": changed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean residual deadline inconsistencies.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
