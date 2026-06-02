"""Rapport cible sur les irritants signales cote utilisateur."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.schemas.device import DeviceSearchParams
from app.services.device_service import DeviceService


VISIBLE_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
VISIBLE_USER_DECISIONS = {None, "publish", "publish_with_caution"}
ACTIONABLE_STATUSES = {"open", "recurring"}
NON_ACTIONABLE_TYPES = {"autre", "institutional_project"}
ENTREPRENEUR_BENEFICIARIES = [
    "entreprise",
    "pme",
    "tpe",
    "mpme",
    "startup",
    "entrepreneur",
    "porteur projet",
    "porteur de projet",
    "jeune entrepreneur",
    "femme entrepreneure",
    "cooperative",
    "entreprise sociale",
    "exploitant agricole",
    "structure_accompagnement",
]
PUBLIC_TYPES = [
    "subvention",
    "pret",
    "avance_remboursable",
    "garantie",
    "credit_impot",
    "exoneration",
    "aap",
    "appel_a_projets",
    "ami",
    "accompagnement",
    "concours",
]
WATCH_TITLES = [
    "TP'up Souveraineté IDF",
    "FCI4Africa - appel 1 jusqu'à 50 000 EUR pour l'innovation alimentaire",
    "FAPE Burkina Faso - cofinancement de projets productifs",
]


def _visible(device: Device) -> bool:
    return (
        device.validation_status in VISIBLE_VALIDATION_STATUSES
        and device.user_quality_decision in VISIBLE_USER_DECISIONS
        and device.status in ACTIONABLE_STATUSES
        and device.device_type not in NON_ACTIONABLE_TYPES
    )


def _entrepreneur(device: Device) -> bool:
    values = set(device.beneficiaries or [])
    return bool(values & set(ENTREPRENEUR_BENEFICIARIES))


def _has_amount(device: Device) -> bool:
    return device.amount_min is not None or device.amount_max is not None or device.funding_rate is not None


def _row(device: Device) -> dict[str, Any]:
    return {
        "id": str(device.id),
        "title": device.title,
        "organism": device.organism,
        "country": device.country,
        "type": device.device_type,
        "status": device.status,
        "amount_min": device.amount_min,
        "amount_max": device.amount_max,
        "currency": device.currency,
        "funding_details": device.funding_details,
        "source_url": device.source_url,
        "beneficiaries": device.beneficiaries,
        "sectors": device.sectors,
        "validation_status": device.validation_status,
        "user_quality_decision": device.user_quality_decision,
    }


async def run() -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).order_by(Device.updated_at.desc().nullslast()))).scalars().all()
        service = DeviceService(db)
        france_result = await service.search(
            DeviceSearchParams(
                countries=["France"],
                beneficiaries=ENTREPRENEUR_BENEFICIARIES,
                device_types=PUBLIC_TYPES,
                status=["open", "recurring"],
                actionable_now=True,
                page=1,
                page_size=200,
                sort_by="relevance",
            )
        )

    visible = [device for device in devices if _visible(device)]
    france_visible = [device for device in visible if device.country == "France"]
    france_entrepreneur = [device for device in france_visible if _entrepreneur(device)]
    france_entrepreneur_public = [device for device in france_entrepreneur if device.device_type in PUBLIC_TYPES]
    france_missing_amount = [device for device in france_entrepreneur_public if not _has_amount(device)]

    watch = []
    for title in WATCH_TITLES:
        matches = [device for device in devices if (device.title or "").lower() == title.lower()]
        watch.extend(_row(device) for device in matches)

    return {
        "france_search_total_for_entrepreneur": france_result["total"],
        "france_visible_actionable": len(france_visible),
        "france_visible_entrepreneur": len(france_entrepreneur),
        "france_visible_entrepreneur_public_types": len(france_entrepreneur_public),
        "france_visible_entrepreneur_public_missing_amount": len(france_missing_amount),
        "france_missing_amount_by_type": dict(Counter(device.device_type for device in france_missing_amount)),
        "france_missing_amount_sample": [_row(device) for device in france_missing_amount[:40]],
        "watched_devices": watch,
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
