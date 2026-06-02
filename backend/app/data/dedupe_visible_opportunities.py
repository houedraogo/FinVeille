"""Dedoublonne des opportunites visibles repetees.

Garde la fiche la plus officielle / la mieux structuree visible cote utilisateur
et masque les copies en admin_only pour eviter les doublons dans les resultats.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

from app.database import AsyncSessionLocal
from app.models.device import Device


DEDUP_GROUPS = [
    {
        "label": "Prix Pierre Castel",
        "keep": UUID("26a7afad-0fdc-488d-98a9-61ffa2482f3d"),
        "hide": [UUID("867f0879-6361-40c0-afa9-118214149486")],
        "reason": "duplicate:prix_pierre_castel",
    },
    {
        "label": "RISE 2 Benin",
        "keep": UUID("559abd90-b9d5-4967-bf89-fd2e4c111ad7"),
        "hide": [UUID("210dee1c-cd5c-4389-9c97-8438c3016774")],
        "reason": "duplicate:rise_2_benin",
    },
    {
        "label": "Digital Energy Challenge",
        "keep": UUID("982d2783-ede4-4f50-85e4-5858c50ab67a"),
        "hide": [UUID("4940cacb-303c-4813-8898-15952ae130b9")],
        "reason": "duplicate:digital_energy_challenge",
    },
]


def _add_tags(device: Device, *tags: str) -> None:
    current = set(device.tags or [])
    current.update(tags)
    device.tags = sorted(current)


async def run() -> dict[str, object]:
    now = datetime.now(timezone.utc)
    result: dict[str, object] = {"groups": []}

    async with AsyncSessionLocal() as db:
        for group in DEDUP_GROUPS:
            kept = await db.get(Device, group["keep"])
            hidden_rows = []

            if kept:
                _add_tags(kept, "dedupe:keeper", group["reason"])
                if kept.validation_status == "admin_only":
                    kept.validation_status = "auto_published"
                if kept.user_quality_decision == "admin_only":
                    kept.user_quality_decision = "publish"
                kept.updated_at = now

            for device_id in group["hide"]:
                device = await db.get(Device, device_id)
                if not device:
                    hidden_rows.append({"id": str(device_id), "status": "not_found"})
                    continue

                before = {
                    "validation_status": device.validation_status,
                    "user_quality_decision": device.user_quality_decision,
                }
                device.validation_status = "admin_only"
                device.user_quality_decision = "admin_only"
                device.user_quality_score = min(device.user_quality_score or 55, 55)
                _add_tags(device, "visibility:admin_only", "dedupe:hidden_duplicate", group["reason"])
                device.updated_at = now
                hidden_rows.append(
                    {
                        "id": str(device.id),
                        "title": device.title,
                        "before": before,
                        "after": {
                            "validation_status": device.validation_status,
                            "user_quality_decision": device.user_quality_decision,
                        },
                    }
                )

            result["groups"].append(
                {
                    "label": group["label"],
                    "kept": str(group["keep"]),
                    "kept_title": kept.title if kept else None,
                    "hidden": hidden_rows,
                }
            )

        await db.commit()

    return result


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
