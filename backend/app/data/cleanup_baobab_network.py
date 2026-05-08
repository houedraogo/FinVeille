"""
Nettoie la fiche Baobab Network deja collectee pour lui appliquer
un titre, un resume et des sections metier propres.

Usage:
    docker exec finveille-backend python -m app.data.cleanup_baobab_network
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


TITLE = "Baobab Network - accelerateur pour startups africaines"
SHORT_DESCRIPTION = (
    "Accelerateur pan-africain pour startups tech, avec candidature en continu "
    "et ticket initial autour de 100 000 USD, combinant investissement, accompagnement "
    "operationnel et acces a un reseau d'investisseurs."
)
PRESENTATION = (
    "Baobab Network accompagne et finance des startups africaines a fort potentiel via un "
    "accelerateur operationnel. Le programme combine premier cheque, appui venture, reseau "
    "international et soutien a la croissance pour des entreprises technologiques en phase early-stage."
)
ELIGIBILITY = (
    "Le programme cible des startups tech orientees business, a but lucratif, qui disposent "
    "idealement d'un MVP et de premiers signes de traction. Les projets en pure idee sont "
    "moins prioritaires et doivent au minimum demontrer une demande de marche deja validee."
)
FUNDING = (
    "Baobab met en avant un ticket initial d'environ 100 000 USD pour accelerer la croissance "
    "de la startup, avec des options complementaires de co-investissement, venture debt et "
    "follow-on fund selon l'evolution de l'entreprise."
)
PROCEDURE = (
    "Les candidatures sont acceptees en continu. La page officielle indique une logique rolling "
    "basis, avec un prochain cohort kick-off mentionne en Q4 2025. Les fondateurs doivent "
    "postuler via la plateforme Baobab."
)
FULL_DESCRIPTION = (
    "## Presentation\n\n"
    f"{PRESENTATION}\n\n"
    "## Criteres d'eligibilite\n\n"
    f"{ELIGIBILITY}\n\n"
    "## Montant / avantages\n\n"
    f"{FUNDING}\n\n"
    "## Demarche\n\n"
    f"{PROCEDURE}\n\n"
    "## Calendrier\n\n"
    "Le programme fonctionne sur un rythme recurrent avec candidatures en continu plutot qu'une "
    "date limite publique unique."
)


async def run() -> None:
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(
                select(Source).where(Source.name == "Baobab Network - accelerator applications")
            )
        ).scalar_one_or_none()
        if not source:
            print("[NOT_FOUND] source")
            return

        devices = (
            await db.execute(
                select(Device)
                .where(Device.source_id == source.id)
                .order_by(Device.created_at.desc())
            )
        ).scalars().all()

        if not devices:
            print("[NOT_FOUND] no devices")
            return

        for device in devices:
            device.title = TITLE
            device.short_description = SHORT_DESCRIPTION
            device.full_description = FULL_DESCRIPTION
            device.eligibility_criteria = ELIGIBILITY
            device.funding_details = FUNDING
            device.device_type = "investissement"
            device.aid_nature = "capital"
            device.country = "Afrique"
            device.region = "Afrique"
            device.zone = "Afrique"
            device.geographic_scope = "continental"
            device.status = "recurring"
            device.is_recurring = True
            device.recurrence_notes = (
                "Le programme fonctionne sans cloture publique unique, avec candidatures en continu."
            )
            device.validation_status = "auto_published"
            device.specific_conditions = (
                "Le programme privilegie les structures for-profit et une preuve de traction "
                "ou de validation de marche."
            )
            device.required_documents = (
                "Le detail du dossier et des informations demandees doit etre confirme sur la "
                "plateforme officielle de candidature Baobab."
            )

        if len(devices) > 1:
            for duplicate in devices[1:]:
                await db.delete(duplicate)

        await db.commit()
        kept = 1 if devices else 0
        removed = max(0, len(devices) - 1)
        print(f"[OK] {kept} fiche Baobab conservee, {removed} doublon(s) supprime(s)")


if __name__ == "__main__":
    asyncio.run(run())
