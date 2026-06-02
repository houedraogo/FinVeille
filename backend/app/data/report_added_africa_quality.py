"""Repere les restes de texte a corriger sur les fiches Afrique ajoutees."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device

from app.data.polish_added_africa_devices import TARGET_DEVICES


PATTERNS = [
    "structurér",
    "confirmér",
    "déposér",
    "présentér",
    "publiér",
    "démarchés",
    "démarché",
    "facilitér",
    "amorçâge",
    "remboursément",
    "a_vérifier",
    "fiche_curée",
]

FIELDS = [
    "title",
    "short_description",
    "full_description",
    "eligibility_criteria",
    "specific_conditions",
    "required_documents",
    "funding_details",
    "recurrence_notes",
    "source_raw",
    "content_sections_json",
    "ai_rewritten_sections_json",
    "decision_analysis",
    "ai_readiness_reasons",
    "user_quality_reasons",
]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


async def run() -> dict[str, Any]:
    titles = [str(device["title"]) for device in TARGET_DEVICES]
    urls = [str(device["source_url"]) for device in TARGET_DEVICES]
    findings: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device).where(
                    or_(
                        Device.title.in_(titles),
                        Device.source_url.in_(urls),
                    )
                )
            )
        ).scalars().all()

        for device in devices:
            for field in FIELDS:
                text = _stringify(getattr(device, field))
                hits = [pattern for pattern in PATTERNS if pattern in text]
                if hits:
                    findings.append(
                        {
                            "id": str(device.id),
                            "title": device.title,
                            "field": field,
                            "patterns": hits,
                        }
                    )

    return {"matched": len(devices), "findings": findings}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
