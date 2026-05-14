from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


SOURCE_NAME = "Tony Elumelu Foundation - entrepreneurship programme"


PRESENTATION = (
    "Le Tony Elumelu Foundation Entrepreneurship Programme soutient les entrepreneurs africains en phase "
    "de démarrage ou de croissance initiale. Le programme combine formation business, mentorat, mise en "
    "réseau panafricaine et capital d'amorçage pour aider les porteurs à structurer et accélérer leur entreprise."
)

ELIGIBILITY = (
    "Le programme s'adresse aux entrepreneurs africains, porteurs d'une entreprise ou d'une idée d'entreprise "
    "à fort potentiel, généralement en phase early-stage. Les candidats doivent confirmer chaque année les pays "
    "éligibles, les secteurs ouverts, les critères d'âge ou de maturité et les conditions de dépôt sur TEFConnect."
)

FUNDING = (
    "Le dispositif associe formation, mentorat, réseau et seed capital pouvant aller jusqu'à 5 000 USD pour les "
    "entrepreneurs sélectionnés, selon les modalités confirmées pour la cohorte en cours."
)

PROCEDURE = (
    "Les candidatures se font via la plateforme officielle TEFConnect lorsque la fenêtre annuelle est ouverte. "
    "Le processus comprend le dépôt du profil, la vérification d'éligibilité, l'évaluation du projet, puis la "
    "sélection des entrepreneurs retenus pour la cohorte."
)

CALENDAR = (
    "Le programme fonctionne par cohortes annuelles ou récurrentes. La source officielle doit être vérifiée pour "
    "confirmer l'ouverture exacte de la prochaine fenêtre de candidature."
)


def _sections() -> list[dict]:
    return [
        {"key": "presentation", "title": "Présentation", "content": PRESENTATION, "confidence": 85, "source": "cleanup_tef"},
        {
            "key": "eligibility",
            "title": "Critères d'éligibilité",
            "content": ELIGIBILITY,
            "confidence": 80,
            "source": "cleanup_tef",
        },
        {"key": "funding", "title": "Montant / avantages", "content": FUNDING, "confidence": 80, "source": "cleanup_tef"},
        {"key": "calendar", "title": "Calendrier", "content": CALENDAR, "confidence": 70, "source": "cleanup_tef"},
        {"key": "procedure", "title": "Démarche", "content": PROCEDURE, "confidence": 80, "source": "cleanup_tef"},
    ]


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if not source:
            return {"updated": 0, "reason": "source_not_found"}

        devices = (
            await db.execute(select(Device).where(Device.source_id == source.id))
        ).scalars().all()

        for device in devices:
            device.title = "Tony Elumelu Foundation - programme entrepreneuriat africain"
            device.short_description = (
                "Programme panafricain pour entrepreneurs early-stage, combinant formation, mentorat, réseau "
                "et seed capital selon les cohortes ouvertes."
            )
            device.full_description = "\n\n".join(
                [
                    f"## Présentation\n{PRESENTATION}",
                    f"## Critères d'éligibilité\n{ELIGIBILITY}",
                    f"## Montant / avantages\n{FUNDING}",
                    f"## Calendrier\n{CALENDAR}",
                    f"## Démarche\n{PROCEDURE}",
                ]
            )
            device.eligibility_criteria = ELIGIBILITY
            device.funding_details = FUNDING
            device.specific_conditions = (
                "La fenêtre de candidature, les critères détaillés et les pièces demandées peuvent varier selon la cohorte annuelle."
            )
            device.required_documents = (
                "Les informations de candidature doivent être confirmées sur TEFConnect ou sur la page officielle du programme."
            )
            device.device_type = "subvention"
            device.aid_nature = "seed_grant"
            device.country = "Afrique"
            device.region = "Afrique"
            device.zone = "Afrique"
            device.geographic_scope = "continental"
            device.beneficiaries = ["entrepreneurs", "startups", "pme"]
            device.sectors = ["entrepreneuriat", "innovation", "transversal"]
            device.status = "recurring"
            device.is_recurring = True
            device.recurrence_notes = CALENDAR
            device.language = "fr"
            device.ai_rewritten_sections_json = _sections()
            device.ai_rewrite_status = "done"
            device.ai_rewrite_model = "local-cleanup-tef-v1"
            device.validation_status = "auto_published"
            device.confidence_score = max(device.confidence_score or 0, 85)
            device.completeness_score = max(device.completeness_score or 0, 86)
            device.ai_readiness_score = max(device.ai_readiness_score or 0, 88)
            device.ai_readiness_label = "pret_pour_recommandation_ia"

        await db.commit()
        return {"updated": len(devices)}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
