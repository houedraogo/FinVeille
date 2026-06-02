from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.database import AsyncSessionLocal


NOW = datetime.now(timezone.utc)


SOURCES: list[dict[str, Any]] = [
    {
        "name": "FAARF Burkina Faso - credit femmes",
        "organism": "Fonds d'Appui aux Activités Rémunératrices des Femmes",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "fonds_public",
        "level": 1,
        "url": "https://faarf.bf/",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "burkina_femmes"},
        "notes": "Fonds public burkinabè dédié à l'accès au crédit des femmes rurales et urbaines.",
    },
    {
        "name": "RESI-2P Burkina Faso - micro-entreprises rurales",
        "organism": "Programme RESI-2P Kakoadb-Jànsùli",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_public",
        "level": 1,
        "url": "https://resi2p.bf/actualite/resi-2p-vers-un-financement-transparent-des-micro-entreprises-rurales/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 4,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "burkina_rural"},
        "notes": "Programme de financement de micro-entreprises rurales, avec sélection 2026 dans les régions de Nando et Yaadga.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "FAARF Burkina Faso - credit femmes",
        "title": "FAARF Burkina Faso - crédits sans garantie pour activités féminines",
        "organism": "Fonds d'Appui aux Activités Rémunératrices des Femmes",
        "organism_type": "fonds public",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "microcredit_femmes",
        "sectors": ["entrepreneuriat", "agriculture", "commerce", "artisanat", "transformation", "elevage"],
        "beneficiaries": ["femme entrepreneure", "entrepreneur", "tpe", "cooperative", "groupement"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://faarf.bf/",
        "source_raw": (
            "Le FAARF est un fonds public burkinabè qui contribue à l'autonomisation économique des femmes par l'accès au crédit. "
            "Il intervient auprès des femmes rurales et urbaines, des coopératives, groupements féminins, associations, groupes de solidarité et femmes individuelles. "
            "Les crédits sont accompagnés de formations et peuvent concerner le commerce, l'agriculture, l'élevage, l'artisanat et la transformation."
        ),
        "presentation": (
            "Le FAARF est une porte d'entrée officielle pour les femmes burkinabè qui cherchent un crédit de proximité afin de développer une activité génératrice de revenus."
        ),
        "eligibility": (
            "La cible concerne les femmes burkinabè rurales ou urbaines exerçant une activité licite, les groupements féminins, associations, coopératives et groupes de solidarité. "
            "La source indique notamment qu'il faut disposer d'une CNIB valide, ne pas être salariée du public ou du privé, et ne pas être déjà engagée auprès d'une structure de financement de l'État."
        ),
        "funding": (
            "Le FAARF propose des crédits de 6 à 24 mois. La source officielle mentionne un taux de 5% pour les crédits de 6 mois et 10% l'an pour les crédits de 24 mois. "
            "Les montants exacts et plafonds doivent être confirmés auprès de l'agence FAARF compétente."
        ),
        "calendar": "Dispositif permanent ou récurrent. Les demandes doivent être confirmées auprès des points FAARF locaux.",
        "procedure": (
            "Consulter le site officiel, identifier le point FAARF le plus proche, vérifier les conditions du produit adapté, puis préparer la CNIB et les informations sur l'activité à financer."
        ),
        "checks": (
            "Confirmer le montant accessible, le calendrier local de dépôt, les pièces demandées, les modalités de remboursement et l'agence compétente avant toute démarche."
        ),
        "decision": (
            "Très bonne piste pour une femme entrepreneure au Burkina Faso qui cherche un crédit de proximité plutôt qu'une subvention ponctuelle."
        ),
    },
    {
        "source_name": "RESI-2P Burkina Faso - micro-entreprises rurales",
        "title": "RESI-2P Burkina Faso - financement de micro-entreprises rurales",
        "organism": "Programme RESI-2P Kakoadb-Jànsùli",
        "organism_type": "programme public",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "local",
        "device_type": "subvention",
        "aid_nature": "microprojet_rural",
        "sectors": ["agriculture", "elevage", "transformation", "commerce rural", "entrepreneuriat"],
        "beneficiaries": ["exploitant agricole", "femme entrepreneure", "jeune entrepreneur", "cooperative", "entrepreneur"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://resi2p.bf/actualite/resi-2p-vers-un-financement-transparent-des-micro-entreprises-rurales/",
        "source_raw": (
            "Le RESI-2P indique avoir lancé en décembre 2025 des appels à projets pour identifier et financer des micro-entreprises rurales. "
            "En 2026, 500 micro-projets individuels et 80 micro-projets collectifs doivent être sélectionnés et financés dans les régions de Nando et Yaadga. "
            "Les financements ciblent en priorité les jeunes, les femmes, les personnes vivant avec un handicap et les personnes déplacées internes."
        ),
        "presentation": (
            "RESI-2P soutient des micro-entreprises rurales au Burkina Faso, avec un mécanisme de sélection et de financement orienté vers les petits producteurs et les activités rurales."
        ),
        "eligibility": (
            "La source cible les micro-entreprises rurales et micro-projets individuels ou collectifs dans les régions de Nando et Yaadga. "
            "Les jeunes, femmes, personnes vivant avec un handicap et personnes déplacées internes sont prioritaires."
        ),
        "funding": (
            "Le programme prévoit le financement de 500 micro-projets individuels et 80 micro-projets collectifs en 2026. "
            "Les montants unitaires, taux de cofinancement et modalités exactes doivent être vérifiés dans les avis ou auprès des structures locales du programme."
        ),
        "calendar": (
            "Le processus 2026 est en phase opérationnelle après les appels lancés fin 2025. Les prochaines fenêtres ou résultats doivent être suivis via le site RESI-2P et les comités locaux."
        ),
        "procedure": (
            "Vérifier auprès de RESI-2P ou des services locaux si une session de candidature est ouverte dans la région concernée, puis préparer l'avant-projet et les informations économiques demandées."
        ),
        "checks": (
            "Confirmer la zone exacte couverte, l'ouverture réelle d'une nouvelle session, les montants, les critères par filière et les contacts officiels avant de conseiller une candidature."
        ),
        "decision": (
            "Piste pertinente pour un porteur de micro-projet rural au Burkina Faso, surtout dans les filières agricoles, transformation ou commerce rural."
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
