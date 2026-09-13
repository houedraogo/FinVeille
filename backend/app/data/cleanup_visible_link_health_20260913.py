"""Masque ou corrige les liens visibles confirmes comme casses le 2026-09-13."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


HIDE_IDS: dict[str, str] = {
    "177690e2-e94d-486a-9877-fdde1e41add1": "Page VC4A retournee en 404 lors de l'audit liens.",
    "0a3a5455-c005-41c1-a86e-75d0aeadc57f": "Page RESI-2P retournee en 404 lors de l'audit liens.",
    "a61fddd8-b209-4177-a789-90a4b6a95621": "Page BIIC/BEI retournee en 404 lors de l'audit liens.",
    "37ae36a9-2f06-4e7f-bdb5-08d4d47fb807": "Page Breizh Angels introuvable lors de l'audit liens.",
    "38fb63ee-9a5f-45d4-930a-d064b55e6ccf": "Domaine Demeter redirige vers un autre site en 404.",
    "5fef54b9-474d-4f5f-aa4b-4e0dfaed4bb8": "Site Fonds Africain pour l'Agriculture retourne 503.",
    "eaa0ee05-d9ea-406b-aa16-7cb0aaba841a": "Site APIM Burkina Faso retourne 503.",
}


def _append_tags(device: Device, *tags: str) -> None:
    current = list(device.tags or [])
    for tag in tags:
        if tag not in current:
            current.append(tag)
    device.tags = current[:30]


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    result: dict[str, Any] = {"dry_run": not apply, "hidden": [], "missing": []}

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(select(Device).where(Device.id.in_(set(HIDE_IDS))))
        ).scalars().all()
        by_id = {str(device.id): device for device in rows}

        for device_id, reason in HIDE_IDS.items():
            device = by_id.get(device_id)
            if not device:
                result["missing"].append(device_id)
                continue

            result["hidden"].append(
                {
                    "id": device_id,
                    "title": device.title,
                    "country": device.country,
                    "source_url": device.source_url,
                    "reason": reason,
                }
            )
            if not apply:
                continue

            device.validation_status = "admin_only"
            device.user_quality_decision = "admin_only"
            device.status = "standby"
            device.decision_analysis = {
                **(device.decision_analysis or {}),
                "visible_link_cleanup_20260913": {
                    "action": "hide",
                    "at": now.isoformat(),
                    "reason": reason,
                },
            }
            _append_tags(device, "visibility:admin_only", "audit:dead_link_hidden", "audit:link_cleanup_20260913")
            device.updated_at = now

        if apply:
            await db.commit()

    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
