"""Ajoute des sources Burkina Faso actionnables a surveiller.

Ces sources sont volontairement ajoutees en mode manuel/qualifie :
elles servent a renforcer le radar Kafundo sans publier automatiquement
des fiches tant qu'un appel precis n'a pas ete verifie.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


SOURCES: list[dict[str, Any]] = [
    {
        "name": "CLE Burkina Faso - entrepreneuriat jeunes",
        "organism": "Cultivons l'Esprit d'Entreprise",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_national",
        "level": 1,
        "url": "https://www.cle-bf.com/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "single_program_page",
            "publication_policy": "manual_review_required",
            "target_countries": ["Burkina Faso"],
            "target_profiles": ["entrepreneur", "startup", "jeune", "femme"],
            "focus": ["entrepreneuriat", "incubation", "subvention", "formation"],
        },
        "notes": (
            "Programme national tres pertinent pour jeunes entrepreneurs au Burkina Faso. "
            "A surveiller pour les nouvelles vagues de formation, incubation, fonds d'amorcage, "
            "prototypage ou demarrage."
        ),
    },
    {
        "name": "PAPEA Burkina Faso - entrepreneuriat agricole",
        "organism": "Programme d'appui a la promotion de l'entrepreneuriat agricole",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_national",
        "level": 1,
        "url": "https://www.papeabf.org/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "single_program_page",
            "publication_policy": "manual_review_required",
            "target_countries": ["Burkina Faso"],
            "target_profiles": ["entrepreneur", "pme", "coopérative", "jeune", "femme"],
            "focus": ["agriculture", "agroalimentaire", "emploi", "accompagnement"],
        },
        "notes": (
            "Programme agricole strategique pour les jeunes, les femmes et les groupes vulnerables. "
            "Source a surveiller pour les appels et mecanismes d'accompagnement des grappes d'entreprises agricoles."
        ),
    },
    {
        "name": "FBDES Burkina Faso - Guichet Teelba",
        "organism": "Fonds Burkinabe de Developpement Economique et Social",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "fonds_public",
        "level": 1,
        "url": "https://www.fbdes.bf/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "single_program_page",
            "publication_policy": "manual_review_required",
            "target_countries": ["Burkina Faso"],
            "target_profiles": ["pme", "coopérative", "association", "entrepreneur"],
            "focus": ["subvention", "credit", "resilience", "developpement local"],
        },
        "notes": (
            "FBDES porte le Guichet Teelba 2024-2026 avec subventions et credits pour projets socio-economiques. "
            "Ne publier que les fenetres d'appel explicitement ouvertes et datees."
        ),
    },
    {
        "name": "ABCA Burkina Faso - Faso Films Fonds",
        "organism": "Agence Burkinabe de la Cinematographie et de l'Audiovisuel",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "fonds_public",
        "level": 1,
        "url": "https://abca.bf/fonds/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "single_program_page",
            "publication_policy": "manual_review_required",
            "target_countries": ["Burkina Faso"],
            "target_profiles": ["entrepreneur", "association", "createur", "pme"],
            "focus": ["culture", "cinema", "audiovisuel", "subvention"],
        },
        "notes": (
            "Faso Films Fonds est un mecanisme public de financement audiovisuel et cinematographique. "
            "A surveiller pour les appels developpement, production, postproduction et export."
        ),
    },
    {
        "name": "HelloPME UEMOA - opportunites PME",
        "organism": "HelloPME",
        "country": "Afrique de l'Ouest",
        "region": "UEMOA",
        "source_type": "agregateur",
        "level": 2,
        "url": "https://hellopme.com/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 4,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "listing",
            "publication_policy": "manual_review_required",
            "target_countries": ["Burkina Faso", "Bénin", "Côte d'Ivoire"],
            "target_profiles": ["pme", "entrepreneur", "startup"],
            "focus": ["financement", "accompagnement", "opportunites", "uemoa"],
        },
        "notes": (
            "Agregateur UEMOA utile pour reperer des opportunites PME. "
            "A utiliser comme source de veille, puis verifier chaque fiche sur la source officielle avant publication."
        ),
    },
    {
        "name": "Service Public Burkina Faso - FASI secteur informel",
        "organism": "Fonds d'Appui au Secteur Informel",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "fonds_public",
        "level": 1,
        "url": "https://servicepublic.gov.bf/fiches/emploi-demande-de-financement-de-micro-projets-du-secteur-informel",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "administrative_procedure",
            "publication_policy": "manual_review_required",
            "target_countries": ["Burkina Faso"],
            "target_profiles": ["microentrepreneur", "secteur informel", "groupement"],
            "focus": ["pret", "microprojet", "emploi", "secteur informel"],
        },
        "notes": (
            "Procedure officielle pour le financement FASI des micro-projets du secteur informel. "
            "Tres concrete pour les petits entrepreneurs burkinabe, a verifier pour les plafonds et antennes locales."
        ),
    },
    {
        "name": "Service Public Burkina Faso - FAIJ entrepreneuriat jeunes",
        "organism": "Fonds d'Appui aux Initiatives des Jeunes",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "fonds_public",
        "level": 1,
        "url": "https://servicepublic.gov.bf/fiches/formation-professionnelle-formation-en-entreprenariat",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "administrative_procedure",
            "publication_policy": "manual_review_required",
            "target_countries": ["Burkina Faso"],
            "target_profiles": ["jeune", "entrepreneur", "porteur projet", "femme"],
            "focus": ["formation", "pret", "subvention", "entrepreneuriat"],
        },
        "notes": (
            "Procedure officielle de formation en entrepreneuriat avec financements FAIJ/PPEJ. "
            "Source utile pour jeunes porteurs de projet, avec montants et taux indiques par le service public."
        ),
    },
    {
        "name": "Service Public Burkina Faso - FAPE cofinancement projets",
        "organism": "Fonds d'Appui a la Promotion de l'Emploi",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "fonds_public",
        "level": 1,
        "url": "https://servicepublic.gov.bf/fiches/emploi-cofinancement-des-projets-agriculture-elevage-artisanat-et-transformation-des-produits-locaux-commerce-prestation-de-service-transport-et-btp",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "administrative_procedure",
            "publication_policy": "manual_review_required",
            "target_countries": ["Burkina Faso"],
            "target_profiles": ["entrepreneur", "pme", "artisan", "agriculteur"],
            "focus": ["cofinancement", "agriculture", "artisanat", "transformation", "emploi"],
        },
        "notes": (
            "Procedure officielle FAPE pour cofinancer des projets productifs dans agriculture, elevage, artisanat, "
            "transformation locale, commerce, services, transport et BTP."
        ),
    },
    {
        "name": "Service Public Burkina Faso - jeunes diplomes microprojets",
        "organism": "Direction Generale de l'Insertion Professionnelle et de l'Emploi",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_public",
        "level": 1,
        "url": "https://www.servicepublic.gov.bf/fiches/emploi-financement-des-microprojets-des-jeunes-diplomes-du-superieur",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "administrative_procedure",
            "publication_policy": "manual_review_required",
            "target_countries": ["Burkina Faso"],
            "target_profiles": ["jeune diplome", "jeune qualifie", "startup", "porteur projet"],
            "focus": ["microprojet", "innovation", "emploi", "insertion professionnelle"],
        },
        "notes": (
            "Procedure officielle pour financer des microprojets innovants portes par des jeunes diplomes "
            "ou jeunes qualifies de centres de formation professionnelle."
        ),
    },
    {
        "name": "FDCT Burkina Faso - appels culture et tourisme",
        "organism": "Fonds de Developpement Culturel et Touristique",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "fonds_public",
        "level": 1,
        "url": "https://www.fdct-bf.org/Appel-a-projets-2025-du-FDCT-Une-opportunite-pour-les-promoteurs-culturels-et",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "call_page",
            "publication_policy": "manual_review_required",
            "target_countries": ["Burkina Faso"],
            "target_profiles": ["entreprise culturelle", "association", "cooperative", "collectivite"],
            "focus": ["culture", "tourisme", "subvention", "credit", "industries creatives"],
        },
        "notes": (
            "Source officielle FDCT pour appels culturels et touristiques. L'appel 2025 indique un volet credit "
            "et un volet subvention ; les prochaines fenetres doivent etre confirmees avant publication en open."
        ),
    },
]


async def run() -> dict[str, Any]:
    result: dict[str, Any] = {"created": [], "updated": [], "unchanged": []}
    async with AsyncSessionLocal() as db:
        for payload in SOURCES:
            existing = (
                await db.execute(select(Source).where(Source.name == payload["name"]))
            ).scalar_one_or_none()
            if existing:
                changed = False
                for key, value in payload.items():
                    if getattr(existing, key) != value:
                        setattr(existing, key, value)
                        changed = True
                result["updated" if changed else "unchanged"].append(payload["name"])
                continue

            db.add(Source(**payload))
            result["created"].append(payload["name"])

        await db.commit()

    return result


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
