from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


SOURCE_NAME = "Global South Opportunities - Funding"
TARGET_TITLE = "Wild Wonder Foundation Micro Grants 2026: Funding for Nature Journaling Clubs Worldwide"


SECTIONS = [
    {
        "key": "presentation",
        "title": "Présentation",
        "content": (
            "Le programme Wild Wonder Foundation Micro Grants 2026 soutient des clubs, éducateurs, "
            "groupes communautaires ou porteurs d'initiatives qui développent la pratique du nature journaling. "
            "L'objectif est de favoriser l'éducation environnementale, la créativité, la connexion à la nature "
            "et l'accès à ces pratiques dans des communautés variées, y compris des publics sous-représentés."
        ),
        "confidence": 90,
        "source": "source_raw",
    },
    {
        "key": "eligibility",
        "title": "Critères d'éligibilité",
        "content": (
            "La fiche s'adresse aux personnes, groupes, clubs ou responsables communautaires qui animent "
            "ou souhaitent structurer une initiative de nature journaling. Les candidatures doivent notamment "
            "présenter un groupe cible, une dynamique de club ou d'activité collective, et une utilisation "
            "cohérente du financement demandé. Les conditions détaillées doivent être vérifiées sur la page "
            "officielle du programme."
        ),
        "confidence": 85,
        "source": "source_raw",
    },
    {
        "key": "funding",
        "title": "Montant / avantages",
        "content": (
            "Le programme propose des micro-subventions. Le montant mentionné dans la fiche peut atteindre "
            "environ 300 USD selon la catégorie et le besoin présenté. Les dépenses admissibles, les plafonds "
            "exacts et les éventuelles contreparties doivent être confirmés sur la source officielle."
        ),
        "confidence": 85,
        "source": "source_raw",
    },
    {
        "key": "calendar",
        "title": "Calendrier",
        "content": (
            "Les candidatures pour le cycle 2026 sont ouvertes depuis le 1er mai 2026. La date limite indiquée "
            "par la source est le 29 mai 2026 à 17h, heure du Pacifique."
        ),
        "confidence": 95,
        "source": "source_raw",
    },
    {
        "key": "procedure",
        "title": "Démarche",
        "content": (
            "La candidature doit être préparée et déposée selon les consignes publiées par la Wild Wonder "
            "Foundation. Il est recommandé de vérifier le formulaire officiel, les catégories de subvention, "
            "les pièces demandées et le fuseau horaire de clôture avant de candidater."
        ),
        "confidence": 85,
        "source": "source_raw",
    },
    {
        "key": "checks",
        "title": "Points à vérifier",
        "content": (
            "Confirmer le montant exact demandé, la catégorie de micro-subvention, les dépenses acceptées, "
            "le fuseau horaire de clôture et les critères finaux directement sur la source officielle."
        ),
        "confidence": 80,
        "source": "source_raw",
    },
]


async def run() -> dict[str, str]:
    async with AsyncSessionLocal() as db:
        device = (
            await db.execute(
                select(Device)
                .join(Source, Device.source_id == Source.id)
                .where(Source.name == SOURCE_NAME, Device.title == TARGET_TITLE)
            )
        ).scalar_one()

        full_description = "\n\n".join(
            f"## {section['title']}\n{section['content']}" for section in SECTIONS
        )

        device.status = "open"
        device.validation_status = "auto_published"
        device.open_date = date(2026, 5, 1)
        device.close_date = date(2026, 5, 29)
        device.is_recurring = False
        device.recurrence_notes = None
        device.device_type = "subvention"
        device.amount_max = device.amount_max or 300
        device.currency = device.currency or "USD"
        device.short_description = (
            "Le programme Wild Wonder Foundation Micro Grants 2026 soutient des initiatives de nature "
            "journaling portées par des clubs, éducateurs ou groupes communautaires. Les candidatures sont "
            "ouvertes jusqu'au 29 mai 2026 à 17h, heure du Pacifique. Le financement peut atteindre environ "
            "300 USD selon la catégorie et doit être confirmé sur la source officielle."
        )
        device.eligibility_criteria = SECTIONS[1]["content"]
        device.funding_details = SECTIONS[2]["content"]
        device.full_description = full_description
        device.content_sections_json = SECTIONS
        device.ai_rewritten_sections_json = SECTIONS
        device.ai_rewrite_status = "done"
        device.ai_rewrite_model = "manual-editorial-fix-v1"
        device.ai_rewrite_checked_at = datetime.now(timezone.utc)
        device.completeness_score = max(device.completeness_score or 0, 92)

        await db.commit()

        return {
            "updated": str(device.id),
            "title": device.title,
            "status": device.status,
            "close_date": str(device.close_date),
        }


def main() -> None:
    import json

    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
