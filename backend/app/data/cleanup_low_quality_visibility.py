"""Aligne la visibilite des fiches dont le score utilisateur exclut la publication."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.services.user_quality import USER_ADMIN_ONLY, USER_REJECT


PUBLIC_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
NON_PUBLIC_DECISIONS = {USER_ADMIN_ONLY, USER_REJECT}


def _mark_hidden(device: Device, now: datetime) -> str:
    tags = set(device.tags or [])
    analysis = dict(device.decision_analysis or {})
    action = "reject" if device.user_quality_decision == USER_REJECT else "admin_only"

    if action == "reject":
        device.validation_status = "rejected"
        device.user_quality_score = 0
        tags.add("visibility:rejected")
    else:
        device.validation_status = "admin_only"
        device.user_quality_score = min(device.user_quality_score or 55, 55)
        tags.add("visibility:admin_only")

    tags.add("quality:low_user_score_hidden")
    analysis["low_quality_visibility_cleanup"] = {
        "action": action,
        "at": now.isoformat(),
        "reason": "user_quality_decision_not_public",
    }
    device.tags = sorted(tags)
    device.decision_analysis = analysis
    device.updated_at = now
    return action


async def run(*, apply: bool = False, limit: int | None = None) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Device)
            .where(
                Device.validation_status.in_(PUBLIC_VALIDATION_STATUSES),
                Device.user_quality_decision.in_(NON_PUBLIC_DECISIONS),
            )
            .order_by(Device.updated_at.desc())
        )
        devices = list(result.scalars().all())
        if limit:
            devices = devices[:limit]

        now = datetime.now(timezone.utc)
        stats: dict[str, Any] = {
            "dry_run": not apply,
            "scanned": len(devices),
            "admin_only": 0,
            "rejected": 0,
            "sample": [],
        }

        for device in devices:
            action = _mark_hidden(device, now)
            if action == "reject":
                stats["rejected"] += 1
            else:
                stats["admin_only"] += 1
            if len(stats["sample"]) < 30:
                stats["sample"].append(
                    {
                        "id": str(device.id),
                        "title": device.title,
                        "status": device.status,
                        "score": device.user_quality_score,
                        "decision": device.user_quality_decision,
                        "validation_status": device.validation_status,
                    }
                )

        if apply:
            await db.commit()
        else:
            await db.rollback()
        return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
