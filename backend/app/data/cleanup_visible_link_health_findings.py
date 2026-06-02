"""Corrige les liens visibles confirmes comme casses par l'audit HTTP."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import compute_completeness, generate_slug, normalize_title


URL_FIXES: dict[str, dict[str, Any]] = {
    "bc680b6a-bc45-4cfa-8be7-cc1e5d18f9b5": {
        "source_url": "https://agirpourlatransition.ademe.fr/entreprises/demarche-decarbonation-industrie/audit-energie-bilan-matiere",
        "source_raw": "Page ADEME active sur l'audit énergétique et le bilan matière.",
    },
    "d5cf8563-2a4c-4756-b703-a13b8a371ea8": {
        "title": "PM'up Île-de-France - transformation écologique et croissance des PME",
        "source_url": "https://www.iledefrance.fr/aides-et-appels-a-projets/pmup",
        "source_raw": "Page officielle Région Île-de-France PM'up.",
    },
    "49449b2f-504e-452f-b4b0-e60c5ae503a3": {
        "source_url": "https://culture.gouv.ci/projets/appel-a-projet-le-guichet-fin-culture-est-officiellement-ouvert/",
        "amount_min": 1_000_000,
        "amount_max": 20_000_000,
        "currency": "XOF",
        "funding_details": "Prêts FIN CULTURE de 1 à 20 millions FCFA pour les industries culturelles et créatives.",
    },
    "d8db6721-4aec-46b4-b903-d125497adbbf": {
        "source_url": "https://culture.gouv.ci/projets/appel-a-candidature-guichet-de-financement-aux-acteurs-du-secteur-de-la-culture/",
        "amount_min": 1_000_000,
        "amount_max": 20_000_000,
        "currency": "XOF",
        "funding_details": "Guichet de financement des acteurs culturels : besoins de financement entre 1 et 20 millions FCFA.",
    },
}

HIDE_IDS = {
    "2e17cee5-a100-45ed-aeec-67ce40c86605": "Site CIFEA retournant une erreur serveur 500 lors de l'audit HTTP.",
}


def _append_tags(device: Device, *tags: str) -> None:
    current = list(device.tags or [])
    for tag in tags:
        if tag not in current:
            current.append(tag)
    device.tags = current[:24]


def _refresh(device: Device) -> None:
    payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
    device.completeness_score = compute_completeness(payload)
    device.title_normalized = normalize_title(device.title)
    device.slug = device.slug or generate_slug(device.title)
    device.updated_at = datetime.now(timezone.utc)


async def run() -> dict[str, Any]:
    result: dict[str, Any] = {"url_fixed": [], "hidden": []}
    ids = set(URL_FIXES) | set(HIDE_IDS)
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).where(Device.id.in_(ids)))).scalars().all()
        for device in devices:
            device_id = str(device.id)
            if device_id in URL_FIXES:
                for field, value in URL_FIXES[device_id].items():
                    setattr(device, field, value)
                _append_tags(device, "audit:link_fixed")
                _refresh(device)
                result["url_fixed"].append({"id": device_id, "title": device.title, "source_url": device.source_url})
            if device_id in HIDE_IDS:
                device.status = "standby"
                device.validation_status = "admin_only"
                device.user_quality_decision = "admin_only"
                device.decision_analysis = {
                    **(device.decision_analysis or {}),
                    "quality_action": "hide_dead_link",
                    "quality_action_at": datetime.now(timezone.utc).isoformat(),
                    "reason": HIDE_IDS[device_id],
                }
                _append_tags(device, "visibility:admin_only", "audit:dead_link_hidden")
                _refresh(device)
                result["hidden"].append({"id": device_id, "title": device.title})

        await db.commit()

    return result


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
