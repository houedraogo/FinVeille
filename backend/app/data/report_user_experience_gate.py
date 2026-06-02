"""Audit de cohérence avant test utilisateur.

Vérifie le parcours critique:
- compteur onboarding public
- résultats réellement affichables
- absence de fiches non candidatables côté utilisateur
- absence de fuite pays évidente entre Burkina, Bénin et Côte d'Ivoire
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.schemas.device import DeviceSearchParams
from app.services.device_service import DeviceService


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

PROFILE_BENEFICIARIES = {
    "entrepreneur": [
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
}

COUNTRY_KEYWORDS = {
    "Burkina Faso": ["burkina", "faso"],
    "Bénin": ["bénin", "benin"],
    "Côte d'Ivoire": ["côte d'ivoire", "cote d'ivoire", "ivoire"],
}


@dataclass(frozen=True)
class Scenario:
    country: str
    profile: str = "entrepreneur"
    sectors: tuple[str, ...] = ("agriculture", "numerique", "energie")


def _text_blob(device: Device) -> str:
    return " ".join(
        [
            device.title or "",
            device.short_description or "",
            device.full_description or "",
            device.eligibility_criteria or "",
            device.funding_details or "",
        ]
    ).lower()


def _country_leaks(country: str, devices: list[Device]) -> list[dict]:
    leaks: list[dict] = []
    for device in devices:
        if device.country not in {"Afrique", "Afrique de l'Ouest"}:
            continue
        blob = _text_blob(device)
        selected_hits = any(keyword in blob for keyword in COUNTRY_KEYWORDS[country])
        for other_country, keywords in COUNTRY_KEYWORDS.items():
            if other_country == country:
                continue
            if any(keyword in blob for keyword in keywords) and not selected_hits:
                leaks.append(
                    {
                        "id": str(device.id),
                        "title": device.title,
                        "country": device.country,
                        "mentioned_country": other_country,
                    }
                )
                break
    return leaks


def _non_publishable(devices: list[Device]) -> list[dict]:
    items: list[dict] = []
    for device in devices:
        reasons = []
        if device.validation_status not in {"auto_published", "approved", "validated"}:
            reasons.append(f"validation_status={device.validation_status}")
        if device.user_quality_decision not in {None, "publish", "publish_with_caution"}:
            reasons.append(f"user_quality_decision={device.user_quality_decision}")
        if device.device_type in {"autre", "institutional_project"}:
            reasons.append(f"device_type={device.device_type}")
        if device.status not in {"open", "recurring"}:
            reasons.append(f"status={device.status}")
        if reasons:
            items.append({"id": str(device.id), "title": device.title, "reasons": reasons})
    return items


async def run() -> dict:
    scenarios = [
        Scenario("Burkina Faso"),
        Scenario("Bénin"),
        Scenario("Côte d'Ivoire"),
    ]
    report = {
        "status": "pass",
        "scenarios": [],
        "summary": {
            "tested": len(scenarios),
            "count_mismatches": 0,
            "non_publishable_items": 0,
            "country_leaks": 0,
        },
    }

    async with AsyncSessionLocal() as db:
        service = DeviceService(db)
        for scenario in scenarios:
            params = DeviceSearchParams(
                countries=[scenario.country],
                sectors=list(scenario.sectors),
                beneficiaries=PROFILE_BENEFICIARIES[scenario.profile],
                device_types=PUBLIC_TYPES,
                status=["open", "recurring"],
                actionable_now=True,
                sort_by="relevance",
                page=1,
                page_size=100,
            )
            result = await service.search(params)
            items = list(result["items"])
            non_publishable = _non_publishable(items)
            leaks = _country_leaks(scenario.country, items)

            expected_count = result["total"]
            displayed_count = len(items) if result["total"] <= params.page_size else result["total"]
            count_ok = expected_count == displayed_count

            if not count_ok:
                report["summary"]["count_mismatches"] += 1
            report["summary"]["non_publishable_items"] += len(non_publishable)
            report["summary"]["country_leaks"] += len(leaks)

            report["scenarios"].append(
                {
                    "country": scenario.country,
                    "profile": scenario.profile,
                    "sectors": list(scenario.sectors),
                    "total": result["total"],
                    "first_page_count": len(items),
                    "count_ok": count_ok,
                    "non_publishable": non_publishable,
                    "country_leaks": leaks,
                    "top_results": [
                        {
                            "title": device.title,
                            "country": device.country,
                            "type": device.device_type,
                            "status": device.status,
                        }
                        for device in items[:8]
                    ],
                }
            )

    if (
        report["summary"]["count_mismatches"]
        or report["summary"]["non_publishable_items"]
        or report["summary"]["country_leaks"]
    ):
        report["status"] = "fail"

    return report


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
