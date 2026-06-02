from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Any

from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.database import AsyncSessionLocal


NOW = datetime.now(timezone.utc)


SOURCES: list[dict[str, Any]] = [
    {
        "name": "SOPA Benin - appel a projets audiovisuels 2026",
        "organism": "Gouvernement du Benin - SOPA",
        "country": "Bénin",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_public",
        "level": 1,
        "url": "https://www.gouv.bj/opportunite/178/appel-projets-coproduction-production-developpement-contenus-audiovisuels-cinematographiques-numeriques-valorisant-benin/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "benin_culture_media"},
        "notes": "Opportunite officielle du Gouvernement du Benin pour reperer des projets audiovisuels, cinema et contenus numeriques.",
    },
    {
        "name": "Orange Summer Challenge 2026",
        "organism": "Orange Digital Center",
        "country": "Afrique",
        "region": "Afrique et Moyen-Orient",
        "source_type": "concours",
        "level": 2,
        "url": "https://osc.gos.orange.com/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 4,
        "category": "private",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "africa_startups_ai"},
        "notes": "Competition officielle Orange Digital Center 2026 pour startups et jeunes talents autour de l'IA.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "SOPA Benin - appel a projets audiovisuels 2026",
        "title": "SOPA Bénin - appel à projets audiovisuels et numériques 2026",
        "organism": "Société de Productions Audiovisuelles (SOPA)",
        "organism_type": "entreprise publique",
        "country": "Bénin",
        "region": "Bénin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "coproduction_audiovisuelle",
        "sectors": ["culture", "media", "audiovisuel", "cinema", "numerique", "intelligence artificielle"],
        "beneficiaries": ["porteur projet", "entrepreneur", "startup", "createur", "pme", "acteur culturel"],
        "open_date": date(2026, 5, 15),
        "close_date": date(2026, 6, 8),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://www.gouv.bj/opportunite/178/appel-projets-coproduction-production-developpement-contenus-audiovisuels-cinematographiques-numeriques-valorisant-benin/",
        "source_raw": (
            "Le Gouvernement du Bénin publie un appel à projets de la SOPA ouvert du 15 mai au 8 juin 2026. "
            "L'appel vise à identifier des projets audiovisuels, cinématographiques et numériques originaux valorisant le Bénin. "
            "La source précise que ce n'est pas une subvention automatique, mais qu'une production, coproduction, visibilité ou appui financier complémentaire peut être mobilisé selon le projet."
        ),
        "presentation": (
            "La SOPA recherche des projets audiovisuels, cinématographiques ou numériques capables de valoriser le Bénin et d'intégrer son catalogue éditorial."
        ),
        "eligibility": (
            "La cible concerne des talents émergents ou confirmés, créateurs, producteurs, porteurs de projets, structures audiovisuelles, cinéma, animation, documentaire ou contenus numériques liés au Bénin."
        ),
        "funding": (
            "L'appel n'est pas présenté comme une subvention directe. Il peut déboucher sur une collaboration avec la SOPA, une production ou coproduction, une mise en visibilité, et éventuellement un appui financier ou co-investissement selon la maturité du projet."
        ),
        "calendar": "Ouverture le 15 mai 2026. Date limite officielle : 8 juin 2026 à 17h00.",
        "procedure": (
            "Consulter la page officielle du Gouvernement du Bénin, télécharger la fiche jointe, préparer le projet audiovisuel ou numérique, puis suivre les modalités de dépôt indiquées par la SOPA."
        ),
        "checks": (
            "Confirmer le format exact du dossier, les pièces à joindre, la propriété intellectuelle, les modalités de production ou coproduction et l'existence éventuelle d'un appui financier."
        ),
        "decision": (
            "Bonne opportunité pour un créateur ou entrepreneur audiovisuel béninois, surtout si le projet peut valoriser le Bénin et entrer dans une logique de production ou coproduction."
        ),
    },
    {
        "source_name": "Orange Summer Challenge 2026",
        "title": "Orange Summer Challenge 2026 - accélération IA pour startups et jeunes talents",
        "organism": "Orange Digital Center",
        "organism_type": "entreprise",
        "country": "Afrique",
        "region": "Afrique",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "concours",
        "aid_nature": "acceleration_startup_ia",
        "sectors": ["intelligence artificielle", "numerique", "startup", "innovation", "technologie"],
        "beneficiaries": ["startup", "jeune entrepreneur", "porteur projet", "jeune talent", "entrepreneur"],
        "open_date": date(2026, 5, 1),
        "close_date": date(2026, 6, 20),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://osc.gos.orange.com/",
        "source_raw": (
            "Orange Summer Challenge 2026 est une compétition du réseau Orange Digital Center organisée dans plusieurs pays d'Afrique et du Moyen-Orient. "
            "L'édition 2026 cible les startups et jeunes talents autour de l'intelligence artificielle comme accélérateur business. "
            "La date limite de candidature publiée sur le site officiel est le 20 juin 2026."
        ),
        "presentation": (
            "Orange Summer Challenge 2026 aide des startups et jeunes talents à transformer des solutions d'intelligence artificielle en réponses concrètes à des besoins business."
        ),
        "eligibility": (
            "La cible concerne les startups et jeunes talents pouvant travailler sur des solutions IA, numériques ou technologiques dans les pays couverts par le réseau Orange Digital Center."
        ),
        "funding": (
            "La valeur principale est l'accès à un programme d'accélération, de co-innovation, d'exposition et de collaboration avec l'écosystème Orange Digital Center. Les éventuelles dotations financières doivent être confirmées sur la page officielle."
        ),
        "calendar": "Les candidatures sont ouvertes pour l'édition 2026. Date limite officielle : 20 juin 2026.",
        "procedure": (
            "Ouvrir le site officiel Orange Summer Challenge, choisir le parcours Startup ou Young Talent, puis compléter le formulaire de candidature avant la date limite."
        ),
        "checks": (
            "Vérifier les pays éligibles, le formulaire adapté au profil, les critères techniques IA, les modalités de participation et les avantages exacts du programme."
        ),
        "decision": (
            "Très bonne piste pour une startup tech ou un jeune talent IA cherchant de la visibilité, un cadre d'accélération et un accès à l'écosystème Orange en Afrique."
        ),
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        sources = {}
        for source_data in SOURCES:
            sources[source_data["name"]] = await upsert_source(db, source_data)

        counts = {"created": 0, "updated": 0}
        for device_data in DEVICES:
            status = await upsert_device(db, device_data, sources[device_data["source_name"]])
            counts[status] += 1

        await db.commit()
        print({"sources": len(sources), **counts})


if __name__ == "__main__":
    asyncio.run(main())
