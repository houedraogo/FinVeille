from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import normalize_title


FIXES: dict[UUID, dict[str, Any]] = {
    UUID("014167ce-857d-4cc4-81ef-caa86014d186"): {
        "title": "Challenge ATF IA pour jeunes innovateurs africains",
        "device_type": "concours",
        "country": "Afrique",
        "validation_status": "auto_published",
        "note": "Titre francise et portee corrigee pour un appel africain actionnable.",
    },
    UUID("26f2bbd7-45de-4c5c-877f-39e019d3a183"): {
        "title": "Subvention du Fonds pour le journalisme d'investigation",
        "device_type": "subvention",
        "validation_status": "auto_published",
        "note": "Titre francise pour une opportunite ouverte avec date fiable.",
    },
    UUID("e86ee50e-fed6-4980-8253-23243698eb30"): {
        "title": "Appel mondial GAFSP pour renforcer la securite alimentaire",
        "validation_status": "admin_only",
        "status": "standby",
        "note": "Masque cote utilisateur : date limite non fiable dans la source collectee.",
    },
    UUID("bb52d7f4-bec1-4d9a-95ee-5715ea8f5229"): {
        "title": "Fonds Development Innovation Ventures pour solutions anti-pauvrete",
        "validation_status": "admin_only",
        "status": "standby",
        "note": "Masque cote utilisateur : appel international sans date exploitable.",
    },
    UUID("bd27a0ac-49fd-4f7a-a29e-f65583700cdd"): {
        "title": "Projet de reponse d'urgence contingente au Togo (CERP)",
        "validation_status": "admin_only",
        "device_type": "institutional_project",
        "note": "Masque cote utilisateur : projet institutionnel Banque mondiale, non candidatable directement.",
    },
}


def _append_tag(device: Device, tag: str) -> None:
    tags = list(device.tags or [])
    if tag not in tags:
        tags.append(tag)
    device.tags = tags


async def run(dry_run: bool = True) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(select(Device).where(Device.id.in_(FIXES.keys())))
        ).scalars().all()

        for device in devices:
            fix = FIXES[device.id]
            before = {
                "title": device.title,
                "status": device.status,
                "validation_status": device.validation_status,
                "device_type": device.device_type,
                "country": device.country,
            }

            new_title = fix.get("title")
            if new_title:
                device.title = new_title
                device.title_normalized = normalize_title(new_title)
                _append_tag(device, "titre_francise")

            for field in ("status", "validation_status", "device_type", "country"):
                if field in fix:
                    setattr(device, field, fix[field])

            analysis = dict(device.decision_analysis or {})
            analysis["public_english_title_cleanup"] = {
                "cleaned_at": now,
                "original_title": before["title"],
                "note": fix.get("note"),
            }
            device.decision_analysis = analysis
            device.last_verified_at = datetime.now(timezone.utc)
            _append_tag(device, "public_title_reviewed")

            rows.append(
                {
                    "id": str(device.id),
                    "before": before,
                    "after": {
                        "title": device.title,
                        "status": device.status,
                        "validation_status": device.validation_status,
                        "device_type": device.device_type,
                        "country": device.country,
                    },
                    "note": fix.get("note"),
                }
            )

        if dry_run:
            await db.rollback()
        else:
            await db.commit()

    return {"dry_run": dry_run, "changed": len(rows), "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoie les 5 titres anglais publics restants.")
    parser.add_argument("--apply", action="store_true", help="Applique les changements en base.")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(dry_run=not args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
