from __future__ import annotations

import asyncio
import json
from collections import Counter

from app.database import AsyncSessionLocal
from app.schemas.device import DeviceSearchParams
from app.services.device_service import DeviceService


TARGET_COUNTRIES = [
    "Burkina Faso",
    "Benin",
    "Bénin",
    "Côte d'Ivoire",
    "Cote d'Ivoire",
    "Afrique de l'Ouest",
    "Afrique",
]

PUBLIC_TYPES = ["subvention", "pret", "aap", "accompagnement", "garantie", "concours"]

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

ENGLISH_MARKERS = (
    "apply by",
    "call for applications",
    "funding opportunity",
    "opens applications",
    "grant for",
    "prize for",
    "challenge for",
)

GENERIC_MARKERS = (
    "les beneficiaires eligibles et les conditions d'acces doivent etre confirmes",
    "le montant exact ou les avantages associes doivent etre confirmes",
    "opportunite de financement relayee",
)


def _text(device) -> str:
    return " ".join(
        [
            device.title or "",
            device.short_description or "",
            device.eligibility_criteria or "",
            device.funding_details or "",
        ]
    ).lower()


def _flags(device) -> list[str]:
    text = _text(device)
    flags: list[str] = []
    if device.status == "standby":
        flags.append("standby_visible")
    if device.device_type in {"institutional_project", "autre"}:
        flags.append("type_non_actionnable")
    if device.validation_status == "admin_only":
        flags.append("admin_only_visible")
    if any(marker in text for marker in ENGLISH_MARKERS):
        flags.append("anglais_residuel")
    if any(marker in text for marker in GENERIC_MARKERS):
        flags.append("texte_trop_generique")
    if not device.close_date and device.status != "recurring":
        flags.append("date_ambigue")
    if not device.eligibility_criteria or len(device.eligibility_criteria.strip()) < 80:
        flags.append("criteres_faibles")
    if not device.funding_details or len(device.funding_details.strip()) < 60:
        flags.append("montant_avantage_faible")
    return flags


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        service = DeviceService(db)
        result = await service.search(
            DeviceSearchParams(
                countries=TARGET_COUNTRIES,
                device_types=PUBLIC_TYPES,
                beneficiaries=ENTREPRENEUR_BENEFICIARIES,
                actionable_now=True,
                sort_by="relevance",
                sort_desc=True,
                page=1,
                page_size=50,
            )
        )

    items = result["items"]
    rows = []
    counts = Counter()
    for device in items:
        flags = _flags(device)
        for flag in flags:
            counts[flag] += 1
        rows.append(
            {
                "id": str(device.id),
                "title": device.title,
                "organism": device.organism,
                "country": device.country,
                "type": device.device_type,
                "status": device.status,
                "close_date": device.close_date.isoformat() if device.close_date else None,
                "validation_status": device.validation_status,
                "flags": flags,
                "short_description": (device.short_description or "")[:220],
            }
        )

    return {
        "scope": "Burkina Faso, Benin, Cote d'Ivoire - utilisateur entrepreneur",
        "total": result["total"],
        "sample_size": len(items),
        "premium_ready": sum(1 for row in rows if not row["flags"]),
        "needs_review": sum(1 for row in rows if row["flags"]),
        "flag_counts": dict(counts),
        "items_to_review": [row for row in rows if row["flags"]][:25],
        "sample": rows[:15],
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
