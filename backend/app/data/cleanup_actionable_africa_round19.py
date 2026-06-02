from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import generate_slug, normalize_title


NOW = datetime.now(timezone.utc)
MODEL = "curation_afrique_round19"


ADMIN_ONLY: dict[str, str] = {
    "Community and Local Development in Western Côte d'Ivoire Project": (
        "Projet institutionnel Banque Mondiale sans lien de candidature directe pour un utilisateur."
    ),
    "Investing for Employment 2026 - subventions de cofinancement en Côte d'Ivoire": (
        "Doublon visible de la fiche Investing for Employment Côte d'Ivoire conservée en version principale."
    ),
}


TITLE_UPDATES: dict[str, dict[str, Any]] = {
    "Presidential African Youth in AI and Robotics Competition 2026: Africa’s Flagship Innovation Platform": {
        "title": "Concours africain jeunesse IA et robotique 2026",
        "short_description": (
            "Ce concours met en avant des jeunes innovateurs africains qui développent des solutions en intelligence artificielle, "
            "robotique ou technologies émergentes. Il est utile pour les startups, étudiants et porteurs de projets tech."
        ),
        "decision_note": (
            "Bonne piste pour les jeunes innovateurs tech, mais il faut confirmer les pays éligibles, le calendrier et la nature exacte des prix sur la source officielle."
        ),
    }
    ,
    "Ouaga Tout Court - incubation pour jeunes cineastes au Burkina Faso": {
        "title": "Ouaga Tout Court - incubation pour jeunes cinéastes au Burkina Faso",
        "short_description": (
            "Ouaga Tout Court accompagne des jeunes cinéastes résidant au Burkina Faso dans le développement et la réalisation "
            "de courts métrages de fiction ou documentaires."
        ),
        "decision_note": (
            "Piste utile pour les entrepreneurs culturels et jeunes cinéastes au Burkina Faso, surtout si le besoin principal est l'accompagnement plutôt qu'une subvention directe."
        ),
    },
    "OIF - soutien a la mobilité des artistes et biens culturels 2026": {
        "title": "OIF - soutien à la mobilité des artistes et biens culturels 2026",
        "decision_note": (
            "Opportunité pertinente pour les acteurs culturels qui doivent financer une mobilité internationale ou la circulation d'œuvres, sous réserve de confirmer les critères sur la source officielle."
        ),
    },
}


SUMMARY_UPDATES: dict[str, str] = {
    "UNIDO A2D Facility - projets de démonstration dans les pays éligibles ODA": (
        "L'A2D Facility de l'UNIDO soutient des projets de démonstration dans des pays éligibles à l'aide publique au développement. "
        "Cette opportunité peut intéresser des structures industrielles ou innovantes capables de tester une solution concrète avec un impact mesurable."
    ),
    "SOE Bénin 2026 - rencontres investisseurs et opportunités business": (
        "SOE Bénin 2026 est un rendez-vous utile pour les entrepreneurs qui cherchent des contacts investisseurs, des partenariats ou de la visibilité business. "
        "La valeur principale est la mise en relation et la préparation commerciale, plus qu'une subvention directe."
    ),
    "Challenge Digital Energy 2026 - PME de l'énergie digitale en Afrique": (
        "Digital Energy Challenge 2026 cible les PME et organisations qui développent des solutions numériques pour l'accès à l'énergie en Afrique. "
        "L'opportunité est pertinente pour les projets combinant innovation, énergie, données et impact terrain."
    ),
    "Choose Africa - financement et accompagnement des PME africaines": (
        "Choose Africa est la porte d'entrée du Groupe AFD et de Proparco pour soutenir les startups, TPE et PME africaines. "
        "L'initiative combine financements, garanties, prises de participation, assistance technique et relais via des partenaires financiers locaux."
    ),
}


def _append_tags(device: Device, *tags: str) -> None:
    current = set(device.tags or [])
    current.update(tags)
    device.tags = sorted(current)


def _mark_admin_only(device: Device, reason: str) -> None:
    device.validation_status = "admin_only"
    device.user_quality_decision = "admin_only"
    device.user_quality_score = min(device.user_quality_score or 0, 40)
    _append_tags(device, "visibility:admin_only", "cleanup:round19", "quality:non_user_actionable")
    analysis = dict(device.decision_analysis or {})
    analysis["public_visibility"] = "admin_only"
    analysis["admin_only_reason"] = reason
    analysis["admin_only_at"] = NOW.isoformat()
    device.decision_analysis = analysis
    device.updated_at = NOW


def _replace_title(device: Device, payload: dict[str, Any]) -> None:
    new_title = payload["title"]
    device.title = new_title
    device.title_normalized = normalize_title(new_title)
    device.slug = generate_slug(new_title)
    if payload.get("short_description"):
        device.short_description = payload["short_description"]
        device.auto_summary = payload["short_description"]
    if payload.get("decision_note"):
        analysis = dict(device.decision_analysis or {})
        analysis["why_interesting"] = payload["decision_note"]
        analysis["points_to_confirm"] = (
            "Confirmer les pays éligibles, le calendrier, les documents demandés et la nature exacte de l'avantage sur la source officielle."
        )
        device.decision_analysis = analysis
    device.language = "fr"
    device.ai_rewrite_status = "done"
    device.ai_rewrite_model = MODEL
    device.ai_rewrite_checked_at = NOW
    _append_tags(device, "cleanup:round19", "translation:title_fr")
    device.updated_at = NOW


def _replace_summary(device: Device, summary: str) -> None:
    device.short_description = summary
    device.auto_summary = summary
    device.ai_rewrite_status = "done"
    device.ai_rewrite_model = MODEL
    device.ai_rewrite_checked_at = NOW
    _append_tags(device, "cleanup:round19", "summary:completed")
    device.updated_at = NOW


async def main() -> None:
    stats = {"admin_only": 0, "translated": 0, "summaries": 0, "missing": []}
    async with AsyncSessionLocal() as db:
        titles = set(ADMIN_ONLY) | set(TITLE_UPDATES) | set(SUMMARY_UPDATES)
        result = await db.execute(select(Device).where(Device.title.in_(titles)))
        devices = {device.title: device for device in result.scalars().all()}

        for title, reason in ADMIN_ONLY.items():
            device = devices.get(title)
            if not device:
                stats["missing"].append(title)
                continue
            _mark_admin_only(device, reason)
            stats["admin_only"] += 1

        for title, payload in TITLE_UPDATES.items():
            device = devices.get(title)
            if not device:
                stats["missing"].append(title)
                continue
            _replace_title(device, payload)
            stats["translated"] += 1

        for title, summary in SUMMARY_UPDATES.items():
            device = devices.get(title)
            if not device:
                stats["missing"].append(title)
                continue
            _replace_summary(device, summary)
            stats["summaries"] += 1

        await db.commit()
    print(stats)


if __name__ == "__main__":
    asyncio.run(main())
