"""Ajoute des sources recurrentes actionnables pour renforcer le lancement Afrique.

Ces fiches ne sont pas des appels ouverts avec date limite. Elles sont publiees
comme opportunites recurrentes lorsque la source permet clairement de candidater,
soumettre un projet ou suivre des appels utiles.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.database import AsyncSessionLocal
from app.data.add_actionable_africa_round3 import upsert_device, upsert_source


SOURCES: list[dict[str, Any]] = [
    {
        "name": "BeoogoLAB Burkina Faso - startup studio",
        "organism": "BeoogoLAB",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "incubateur",
        "level": 1,
        "url": "https://www.beoogolab.org/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 4,
        "category": "private",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "burkina_startups"},
        "notes": "Startup studio burkinabe avec bouton de soumission de projet, accompagnement, financement et expertise.",
    },
    {
        "name": "AJECI Incub Cote d'Ivoire - jeunes entrepreneurs",
        "organism": "Association des Jeunes Entrepreneurs de Cote d'Ivoire",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "source_type": "incubateur",
        "level": 1,
        "url": "https://ajeci-ci.org/public/Incubateur",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 4,
        "category": "private",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "cote_ivoire_jeunes_entrepreneurs"},
        "notes": "Incubateur AJECI pour projets innovants de jeunes entrepreneurs, concours, appels a projets et mentoring.",
    },
    {
        "name": "ABF Burkina Faso - appels a projets OSC et associations",
        "organism": "Action Burkinabe de Fundraising",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "ong",
        "level": 1,
        "url": "https://www.abfburkina.org/appels-a-projets/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 4,
        "category": "private",
        "is_active": True,
        "config": {"source_kind": "listing", "market": "burkina_osc_ong"},
        "notes": "Source locale utile pour appels a projets, crowdfunding et mobilisation de ressources pour OSC et associations.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "BeoogoLAB Burkina Faso - startup studio",
        "title": "BeoogoLAB Burkina Faso - financement et accompagnement de startups numériques",
        "organism": "BeoogoLAB",
        "organism_type": "startup studio",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "startup_studio",
        "sectors": ["numerique", "agriculture", "sante", "education", "fintech", "culture"],
        "beneficiaries": ["startup", "entrepreneur", "porteur projet", "pme innovante"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.beoogolab.org/",
        "source_raw": (
            "BeoogoLAB indique lancer, financer et accompagner des initiatives entrepreneuriales innovantes "
            "basees sur le numerique, avec un bouton officiel pour soumettre un projet."
        ),
        "presentation": (
            "BeoogoLAB est un startup studio base au Burkina Faso. Il aide des initiatives entrepreneuriales "
            "innovantes a se structurer, se financer, recruter, accelerer leur developpement et acceder a de "
            "l'expertise."
        ),
        "eligibility": (
            "La source cible principalement des porteurs de projets et startups au Burkina Faso, en particulier "
            "des solutions numeriques ayant un impact dans l'agriculture, la sante, l'education, l'inclusion "
            "financiere, la culture ou les services."
        ),
        "funding": (
            "L'appui peut inclure accompagnement, expertise et ressources financieres pour les jeunes entreprises "
            "retenues. Le montant et la forme exacte de l'investissement dependent de l'analyse du projet."
        ),
        "calendar": (
            "Dispositif recurrent: la soumission de projet peut etre faite via la plateforme BeoogoLAB, sans "
            "fenetre de cloture unique publiee."
        ),
        "procedure": (
            "Utiliser le bouton officiel Soumettre un projet, presenter l'idee ou la startup, puis attendre "
            "l'analyse par l'equipe BeoogoLAB."
        ),
        "checks": (
            "Verifier que le formulaire de soumission est actif, que le projet correspond aux secteurs cibles "
            "et que les conditions financieres sont clarifiees avant engagement."
        ),
        "decision": (
            "Bonne piste pour une startup numerique au Burkina Faso qui cherche un accompagnement profond, pas "
            "seulement une subvention ponctuelle."
        ),
    },
    {
        "source_name": "AJECI Incub Cote d'Ivoire - jeunes entrepreneurs",
        "title": "AJECI'Incub Côte d'Ivoire - incubation de projets innovants jeunes",
        "organism": "Association des Jeunes Entrepreneurs de Cote d'Ivoire",
        "organism_type": "association entrepreneuriale",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "incubation",
        "sectors": ["entrepreneuriat", "innovation", "formation", "mentorat", "pme"],
        "beneficiaries": ["jeune entrepreneur", "porteur projet", "startup", "entrepreneur"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://ajeci-ci.org/public/Incubateur",
        "source_raw": (
            "AJECI'Incub vise a faire incuber des projets innovants de jeunes entrepreneurs. La selection peut "
            "prendre la forme d'un concours ou d'un appel a projets, avec mentoring."
        ),
        "presentation": (
            "AJECI'Incub est une piste d'incubation pour les jeunes entrepreneurs ivoiriens qui portent un projet "
            "innovant et cherchent a le structurer avec un reseau entrepreneurial."
        ),
        "eligibility": (
            "La cible principale est composee de jeunes entrepreneurs, membres ou candidats AJECI, avec un projet "
            "innovant pouvant etre presente dans le cadre d'un concours ou d'un appel a projets."
        ),
        "funding": (
            "L'appui porte surtout sur l'incubation, le mentoring, l'acces reseau et la selection de projets. La "
            "source ne communique pas de subvention directe garantie."
        ),
        "calendar": (
            "Dispositif recurrent: les dates de concours ou d'appel a projets sont definies par AJECI selon les "
            "sessions."
        ),
        "procedure": (
            "Contacter AJECI ou suivre la page Incubateur, verifier la session ouverte puis deposer le dossier "
            "selon la procedure annoncee."
        ),
        "checks": (
            "Confirmer la session ouverte, l'adhesion eventuelle a AJECI, les criteres du concours et les "
            "benefices concrets avant de candidater."
        ),
        "decision": (
            "Piste utile pour un jeune entrepreneur en Cote d'Ivoire qui veut integrer un reseau et faire "
            "progresser un projet innovant."
        ),
    },
    {
        "source_name": "ABF Burkina Faso - appels a projets OSC et associations",
        "title": "ABF Burkina Faso - veille d'appels à projets pour OSC et associations",
        "organism": "Action Burkinabe de Fundraising",
        "organism_type": "association",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "veille_financement",
        "sectors": ["ong", "association", "developpement local", "formation", "fundraising"],
        "beneficiaries": ["association", "ong", "organisation locale", "collectivite", "porteur projet"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.abfburkina.org/appels-a-projets/",
        "source_raw": (
            "Action Burkinabe de Fundraising accompagne les associations et collectivites territoriales dans la "
            "mobilisation des ressources et publie des appels a projets et opportunites."
        ),
        "presentation": (
            "ABF est une source locale utile pour les associations, ONG et structures communautaires au Burkina "
            "Faso qui cherchent des appels a projets, formations et opportunites de mobilisation de ressources."
        ),
        "eligibility": (
            "La source est surtout pertinente pour les OSC, associations, ONG locales, collectivites et porteurs "
            "de projets communautaires qui cherchent des financements ou partenaires."
        ),
        "funding": (
            "ABF ne finance pas toujours directement; la valeur principale est l'acces a des appels a projets, "
            "opportunites de cofinancement, formations de fundraising et informations partenaires."
        ),
        "calendar": (
            "Source recurrente: les opportunites sont publiees au fil de l'eau dans la rubrique Appels a Projets."
        ),
        "procedure": (
            "Suivre la page officielle ABF, ouvrir l'appel pertinent, verifier les criteres et candidater sur la "
            "source finale indiquee."
        ),
        "checks": (
            "Verifier que l'appel relaye est encore ouvert, que la source finale est fiable et que le pays ou le "
            "type d'organisation est bien eligible."
        ),
        "decision": (
            "Bonne source de veille pour les ONG et associations burkinabe, a utiliser pour reperer des appels "
            "concrets plutot que comme guichet de financement unique."
        ),
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        sources = {}
        for source_data in SOURCES:
            sources[source_data["name"]] = await upsert_source(db, source_data)

        created = 0
        updated = 0
        for device_data in DEVICES:
            action = await upsert_device(db, device_data, sources[device_data["source_name"]])
            created += int(action == "created")
            updated += int(action == "updated")
        await db.commit()
    print({"sources": len(sources), "created": created, "updated": updated})


if __name__ == "__main__":
    asyncio.run(main())
