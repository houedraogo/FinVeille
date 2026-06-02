"""Corrige les bloqueurs qualité repérés le 21/05/2026.

Actions ciblées :
- expire les fiches encore "open" avec date passée ;
- masque les fiches visibles avec lien mort ou date passée ;
- remet en admin_only les projets Banque Mondiale publiés par erreur.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.visible_quality_service import build_visible_quality_audit


WORLD_BANK_SOURCE_PREFIX = "Banque Mondiale - projets"


def _append_tags(device: Device, *tags: str) -> None:
    current = set(device.tags or [])
    current.update(tags)
    device.tags = sorted(current)


def _hide(device: Device, reason: str) -> None:
    device.validation_status = "admin_only"
    device.user_quality_decision = "admin_only"
    device.user_quality_score = min(device.user_quality_score or 55, 55)
    _append_tags(device, "visibility:admin_only", reason)


async def run(*, apply: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = date.today()
    result: dict[str, Any] = {
        "dry_run": not apply,
        "expired_open_with_past_date": [],
        "hidden_expired_public": [],
        "hidden_visible_quality": [],
        "hidden_world_bank_public": [],
    }

    async with AsyncSessionLocal() as db:
        past_open = (
            await db.execute(
                select(Device, Source)
                .outerjoin(Source, Source.id == Device.source_id)
                .where(Device.status == "open", Device.close_date.is_not(None), Device.close_date < today)
                .order_by(Device.close_date.asc(), Device.title.asc())
            )
        ).all()

        for device, source in past_open:
            before_status = device.status
            before_validation_status = device.validation_status
            device.status = "expired"
            device.is_recurring = False
            if device.validation_status in {"auto_published", "approved", "validated"}:
                _hide(device, "launch_blocker:expired_public_admin_only")
                result["hidden_expired_public"].append(
                    {
                        "id": str(device.id),
                        "title": device.title,
                        "source": source.name if source else None,
                        "close_date": str(device.close_date),
                        "before_validation_status": before_validation_status,
                        "after_validation_status": device.validation_status,
                    }
                )
            device.updated_at = now
            result["expired_open_with_past_date"].append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "source": source.name if source else None,
                    "close_date": str(device.close_date),
                    "before_status": before_status,
                    "after_status": device.status,
                    "validation_status": before_validation_status,
                }
            )

        audit = await build_visible_quality_audit(db, limit=80)
        for item in audit.get("items", []):
            issues = set(item.get("issues") or [])
            if not (issues & {"expired_visible", "dead_link", "admin_only_visible", "no_source", "unqualified_type"}):
                continue
            device = await db.get(Device, item["id"])
            if not device:
                continue
            _hide(device, "launch_blocker:hidden_visible_quality")
            device.updated_at = now
            result["hidden_visible_quality"].append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "issues": sorted(issues),
                    "source": item.get("source_name"),
                }
            )

        public_world_bank = (
            await db.execute(
                select(Device, Source)
                .join(Source, Source.id == Device.source_id)
                .where(
                    Source.name.ilike(f"{WORLD_BANK_SOURCE_PREFIX}%"),
                    Device.validation_status.in_(["auto_published", "approved", "validated"]),
                )
                .order_by(Device.country.asc(), Device.title.asc())
            )
        ).all()

        for device, source in public_world_bank:
            _hide(device, "launch_blocker:world_bank_institutional_admin_only")
            device.updated_at = now
            result["hidden_world_bank_public"].append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "country": device.country,
                    "source": source.name,
                }
            )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Corrige les bloqueurs lancement Kafundo.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
