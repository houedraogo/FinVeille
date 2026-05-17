from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import normalize_title


PROMOTE = {
    UUID("67584424-1a91-4304-9620-dca0508aa956"): {
        "title": "Accélérateur RAISEAfrica 2026 pour startups des énergies renouvelables",
        "country": "Afrique du Sud",
        "close_date": date(2026, 5, 17),
        "device_type": "concours",
        "why": "Date limite détectée dans le texte brut : 17 mai 2026.",
    },
    UUID("2947dedc-cb1e-4d59-a8ee-8fbb455b4a2f"): {
        "title": "Bourse agricole 2027 pour étudiants en Afrique du Sud",
        "country": "Afrique du Sud",
        "close_date": date(2026, 9, 30),
        "device_type": "subvention",
        "why": "Date limite détectée dans le texte brut : 30 septembre 2026.",
    },
    UUID("14d47b91-211f-48b2-95a5-9e41f3a07c02"): {
        "title": "Financement PESP 7 pour projets créatifs en Afrique du Sud",
        "country": "Afrique du Sud",
        "close_date": date(2026, 5, 29),
        "device_type": "subvention",
        "why": "Date limite détectée dans le texte brut : 29 mai 2026.",
    },
    UUID("4940cacb-303c-4813-8898-15952ae130b9"): {
        "title": "Digital Energy Challenge 2026 pour PME de l'énergie en Afrique",
        "country": "Afrique",
        "close_date": date(2026, 6, 17),
        "device_type": "subvention",
        "why": "Date limite détectée dans le texte brut : 17 juin 2026.",
    },
    UUID("edecd53e-40bd-4493-9dd8-be0baab8d20e"): {
        "title": "Subventions PyCon Africa 2026 pour participation inclusive à Kampala",
        "country": "Ouganda",
        "close_date": date(2026, 6, 1),
        "device_type": "subvention",
        "why": "Date limite détectée dans le texte brut : 1er juin 2026.",
    },
}

TITLE_ONLY = {
    UUID("e10b4fb1-10b5-46a1-9832-6595cc0e1140"): "Appel Agog 2026 pour projets climat et médias immersifs",
    UUID("bf6346d1-e3a3-4dd0-b4d8-10fc469d6b97"): "Programme Connected Futures 2026 pour organisations à impact social aux États-Unis",
    UUID("dc7d2aca-a66c-4236-b145-947fdf1ab089"): "Falling Walls Lab Gauteng 2026 pour jeunes innovateurs",
    UUID("c8e8390e-8222-45fa-bab6-5a494788091c"): "Prix environnemental RELX 2026 pour l'eau, l'assainissement et l'océan",
    UUID("e750818d-149f-4e3f-b069-53d72fa5b5a7"): "Subvention bien-être pour enseignants noirs - Black Teacher Project 2026",
    UUID("57915c78-0026-4011-9f50-c32455756e22"): "Prix UN SDG Action Awards 2026 - héros de demain",
}


def _set_title(device: Device, title: str) -> None:
    device.title = title
    device.title_normalized = normalize_title(title)
    tags = list(device.tags or [])
    if "titre_francise" not in tags:
        tags.append("titre_francise")
    device.tags = tags


async def run(dry_run: bool = True) -> dict:
    target_ids = set(PROMOTE) | set(TITLE_ONLY)
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(select(Device).where(Device.id.in_(target_ids)))
        ).scalars().all()

        rows = []
        now = datetime.now(timezone.utc).isoformat()
        for device in devices:
            before = {
                "title": device.title,
                "status": device.status,
                "validation_status": device.validation_status,
                "close_date": device.close_date.isoformat() if device.close_date else None,
                "country": device.country,
            }

            action = "title_only"
            if device.id in PROMOTE:
                spec = PROMOTE[device.id]
                action = "promoted"
                if not dry_run:
                    _set_title(device, spec["title"])
                    device.country = spec["country"]
                    device.close_date = spec["close_date"]
                    device.status = "open"
                    device.validation_status = "auto_published"
                    device.device_type = spec["device_type"]
                    device.confidence_score = max(device.confidence_score or 0, 82)
                    device.completeness_score = max(device.completeness_score or 0, 72)
                    tags = list(device.tags or [])
                    for tag in [
                        "source:global_south_requalified",
                        "deadline:verified_from_raw",
                        "quality:manual_requalified",
                    ]:
                        if tag not in tags:
                            tags.append(tag)
                    device.tags = tags
                    analysis = dict(device.decision_analysis or {})
                    analysis["go_no_go"] = "go"
                    analysis["priority"] = "medium"
                    analysis["why_interesting"] = (
                        "Opportunité africaine conservée car la date limite est explicite "
                        "dans le contenu source."
                    )
                    analysis["recommended_action"] = (
                        "Vérifier les conditions sur la source officielle puis décider "
                        "rapidement si l'opportunité correspond au projet."
                    )
                    analysis["manual_requalification"] = {
                        "checked_at": now,
                        "reason": spec["why"],
                    }
                    device.decision_analysis = analysis
            elif device.id in TITLE_ONLY and not dry_run:
                _set_title(device, TITLE_ONLY[device.id])
                analysis = dict(device.decision_analysis or {})
                analysis["title_cleanup"] = {
                    "title_fr_cleaned_at": now,
                    "original_title": before["title"],
                    "cleanup_scope": "global_south_pending_title_only",
                }
                device.decision_analysis = analysis

            rows.append(
                {
                    "id": str(device.id),
                    "action": action,
                    "before": before,
                    "after_title": PROMOTE.get(device.id, {}).get("title")
                    or TITLE_ONLY.get(device.id),
                    "after_close_date": PROMOTE.get(device.id, {}).get("close_date"),
                }
            )

        if dry_run:
            await db.rollback()
        else:
            await db.commit()

    return {"dry_run": dry_run, "changed": len(rows), "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Requalifie les meilleures fiches Global South en attente.")
    parser.add_argument("--apply", action="store_true", help="Applique les changements en base.")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(dry_run=not args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
