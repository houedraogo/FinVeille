"""
Nettoie et publie la fiche I&P issue de la collecte.

Usage:
    docker exec finveille-backend python -m app.data.cleanup_ietp
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


TITLE = "I&P - financement et accompagnement des PME africaines"
SHORT_DESCRIPTION = (
    "Investisseur d'impact dedie aux PME et start-ups d'Afrique subsaharienne, "
    "avec besoins de financement typiquement compris entre 300 000 EUR et 1,5 M EUR."
)
PRESENTATION = (
    "Investisseurs & Partenaires (I&P) est un groupe pionnier de l'investissement d'impact "
    "dedie au financement et a l'accompagnement des petites et moyennes entreprises en Afrique "
    "subsaharienne. L'approche combine capital, conseil strategique et appui operationnel."
)
ELIGIBILITY = (
    "Le dispositif cible des PME et start-ups basees en Afrique subsaharienne ou dans l'ocean Indien, "
    "gerees par des equipes locales, relevant de l'economie formelle et actives dans des secteurs varies "
    "comme la sante, l'agrobusiness, la distribution, la finance, les services, l'energie ou les TIC."
)
FUNDING = (
    "I&P intervient comme investisseur minoritaire avec plusieurs vehicules d'investissement. "
    "La page de soumission mentionne des besoins de financement typiquement entre 300 000 EUR et 1,5 M EUR, "
    "avec des cas inferieurs a 300 000 EUR selon les dispositifs."
)
PROCEDURE = (
    "Les entrepreneurs peuvent soumettre directement leur business plan sur la page officielle I&P. "
    "L'etude preliminaire d'une demande prend en moyenne 2 a 3 semaines, et l'equipe d'investissement "
    "reprend contact si le projet correspond aux criteres annonces."
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
    "I&P fonctionne comme un investisseur recurrent, sans date limite publique unique pour soumettre un projet."
)


async def run() -> None:
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(
                select(Source).where(Source.name == "I&P - soumettre votre business plan")
            )
        ).scalar_one_or_none()
        if not source:
            print("[NOT_FOUND] source")
            return

        devices = (
            await db.execute(select(Device).where(Device.source_id == source.id))
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
            device.status = "recurring"
            device.is_recurring = True
            device.validation_status = "auto_published"
            device.recurrence_notes = (
                "I&P fonctionne comme un investisseur recurrent, sans date limite publique unique."
            )
            device.device_type = "investissement"
            device.aid_nature = "capital"
            device.country = "Afrique"
            device.region = "Afrique"
            device.zone = "Afrique"
            device.geographic_scope = "continental"
            device.organism = "Investisseurs & Partenaires"
            device.specific_conditions = (
                "Le projet doit relever de l'economie formelle et etre porte par une equipe locale "
                "avec un besoin de financement coherent avec les vehicules I&P."
            )
            device.required_documents = (
                "Business plan, presentation de l'entreprise et elements complementaires a confirmer "
                "sur la page officielle de soumission I&P."
            )

        await db.commit()
        print(f"[OK] {len(devices)} fiche(s) I&P nettoyee(s)")


if __name__ == "__main__":
    asyncio.run(run())
