from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import normalize_title


TITLE_BY_ID = {
    UUID("747e9eb6-9a27-44be-9a54-13caa6bce7a5"): "EU Hardwoods - bois feuillus européens pour le bâtiment",
    UUID("f582ad91-a8d2-419d-bf77-3fde790e8bf6"): "Prix Wellcome Accelerator 2026 pour chercheurs basés au Royaume-Uni",
    UUID("8b6ab2dc-7eed-46ba-ab38-59174dfef050"): "Programme EdTech de la Mastercard Foundation - Bénin",
    UUID("42e7e4b2-e87e-48e5-b3d0-73a6d3f97015"): "Prix PEEB Burkina Faso pour entrepreneurs et industriels",
    UUID("d648e6e6-88c9-4293-ae41-ad2919df5521"): "Challenge numérique AFD",
    UUID("1676b225-574d-43f6-b43e-53cc10b9102f"): "Programme Echoing Green pour entrepreneurs sociaux",
    UUID("4562e834-88d6-4cea-8af2-33ddd2f3eec7"): "FID - Fonds pour l'innovation dans le développement",
    UUID("c961766e-f775-457b-875e-eca45cc67e78"): "Fonds d'innovation GSMA",
    UUID("790dac3b-d286-4f73-a9e7-1ce06f44bb7a"): "Programme Rainer Arnhold de la Mulago Foundation",
    UUID("a377d8c6-b7f8-482b-b831-0a87a51da1b2"): "Programme d'innovation Funguo - catalyseur vert",
}


async def run(dry_run: bool = True) -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(select(Device).where(Device.id.in_(TITLE_BY_ID.keys())))
        ).scalars().all()

        rows = []
        for device in devices:
            new_title = TITLE_BY_ID.get(device.id)
            if not new_title or device.title == new_title:
                continue

            old_title = device.title
            rows.append(
                {
                    "id": str(device.id),
                    "old_title": old_title,
                    "new_title": new_title,
                    "validation_status": device.validation_status,
                }
            )
            if dry_run:
                continue

            device.title = new_title
            device.title_normalized = normalize_title(new_title)
            tags = list(device.tags or [])
            if "titre_francise" not in tags:
                tags.append("titre_francise")
            device.tags = tags
            analysis = dict(device.decision_analysis or {})
            analysis["title_cleanup"] = {
                "title_fr_cleaned_at": datetime.now(timezone.utc).isoformat(),
                "original_title": old_title,
                "cleanup_scope": "remaining_public_titles",
            }
            device.decision_analysis = analysis

        if dry_run:
            await db.rollback()
        else:
            await db.commit()

    return {"dry_run": dry_run, "changed": len(rows), "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoie les derniers titres publics anglais.")
    parser.add_argument("--apply", action="store_true", help="Applique les changements en base.")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(dry_run=not args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
