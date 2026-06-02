from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.database import AsyncSessionLocal
from app.models.device import Device


NOW = datetime.now(timezone.utc)


VC4A_TOO_GENERIC = [
    "Prix PRIMA Jeunes Innovateurs 2026",
    "iF Social Impact Prize 2026",
    "Challenge mondial d'impact THRIVE 2026",
    "Programme d'innovation Funguo - catalyseur vert",
]


SOURCES: list[dict[str, Any]] = [
    {
        "name": "CLE Burkina Faso - entrepreneuriat jeunes",
        "organism": "Cultivons l'Esprit d'Entreprise",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_entrepreneuriat",
        "level": 1,
        "url": "https://www.cle-bf.com/",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "burkina_jeunes"},
        "notes": "Programme officiel de promotion de l'entrepreneuriat des jeunes au Burkina Faso, financé par le Royaume des Pays-Bas.",
    },
    {
        "name": "GUDE-PME Cote d'Ivoire - programmes PME",
        "organism": "GUDE-PME",
        "country": "Côte d'Ivoire",
        "region": "Afrique de l'Ouest",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://gudepme.ci/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "cote_ivoire_pme"},
        "notes": "Guichet Unique de Développement des PME: programmes de bancabilité, inclusion financière, accès aux marchés et compétitivité PME.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "CLE Burkina Faso - entrepreneuriat jeunes",
        "title": "CLE Burkina Faso - formation, incubation et fonds d'amorçage pour jeunes entrepreneurs",
        "organism": "Cultivons l'Esprit d'Entreprise",
        "organism_type": "programme entrepreneuriat",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "incubation_et_seed",
        "sectors": ["entrepreneuriat", "agro-industrie", "services", "technologie", "energie", "artisanat"],
        "beneficiaries": ["jeune entrepreneur", "porteur projet", "startup", "entrepreneur", "femme entrepreneure"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.cle-bf.com/",
        "source_raw": "CLE est un programme de promotion de l'entrepreneuriat des jeunes au Burkina Faso, financé par le Royaume des Pays-Bas. Il cible les jeunes hommes et femmes de 18 à 35 ans et prévoit formation, idéation, incubation et accès à des fonds d'amorçage, de prototypage ou de démarrage.",
        "presentation": "CLE accompagne les jeunes entrepreneurs burkinabè de l'idée au lancement d'entreprise. Le programme combine formation, idéation, incubation, réseau entrepreneurial et appui au démarrage dans plusieurs secteurs productifs.",
        "eligibility": "La cible principale est composée de jeunes hommes et femmes de 18 à 35 ans au Burkina Faso, notamment dans les zones urbaines et périurbaines. Les projets peuvent concerner l'agro-industrie, les services, les technologies, les énergies renouvelables ou l'artisanat.",
        "funding": "Les projets sélectionnés peuvent bénéficier d'un accompagnement technique et stratégique, puis accéder à des subventions complémentaires sous forme de fonds d'amorçage, de prototypage ou de démarrage. Les montants exacts dépendent des cohortes et sélections.",
        "calendar": "Programme récurrent à surveiller selon les campagnes, formations, sessions d'idéation et cohortes d'incubation.",
        "procedure": "Consulter le site officiel CLE, suivre les annonces de campagnes ou de formations, puis déposer sa candidature quand une session est ouverte dans la zone concernée.",
        "checks": "Confirmer la zone d'intervention, l'âge requis, la session ouverte, les pièces demandées et la disponibilité effective des fonds avant de candidater.",
        "decision": "Très bonne piste pour un jeune porteur de projet au Burkina Faso qui cherche un accompagnement complet et une première aide au démarrage.",
    },
    {
        "source_name": "GUDE-PME Cote d'Ivoire - programmes PME",
        "title": "GUDE-PME Côte d'Ivoire - bancabilité, financement et accès aux marchés PME",
        "organism": "GUDE-PME",
        "organism_type": "agence nationale",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "appui_pme",
        "sectors": ["entrepreneuriat", "pme", "finance", "marche", "innovation", "industrie"],
        "beneficiaries": ["pme", "tpe", "entrepreneur", "startup", "entreprise", "femme entrepreneure"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://gudepme.ci/",
        "source_raw": "Le GUDE-PME présente des programmes de bancabilité et inclusion financière, d'accès des PME aux marchés, de compétitivité, qualité et chaînes de valeur. Il se positionne comme guichet de soutien, financement et innovation des PME en Côte d'Ivoire.",
        "presentation": "Le GUDE-PME est une porte d'entrée publique pour les PME ivoiriennes qui veulent améliorer leur bancabilité, accéder à des financements, se connecter à des marchés et renforcer leur compétitivité.",
        "eligibility": "Cette piste concerne les PME, TPE, startups et entrepreneurs ivoiriens ayant besoin d'appui pour structurer leur entreprise, améliorer leur accès au financement ou accéder à de nouveaux marchés.",
        "funding": "L'appui est principalement de l'accompagnement: bancabilité, inclusion financière, accès aux marchés, compétitivité, qualité, chaînes de valeur et orientation vers les programmes PME pertinents. Les financements directs doivent être confirmés programme par programme.",
        "calendar": "Source récurrente: les programmes et événements sont publiés au fil de l'eau par le GUDE-PME.",
        "procedure": "Consulter les programmes sur le site officiel, identifier le programme adapté, puis contacter le GUDE-PME ou suivre la procédure de candidature indiquée pour la session ouverte.",
        "checks": "Vérifier le programme actif, les critères sectoriels, les documents exigés, la forme exacte de l'appui et l'existence d'un financement direct.",
        "decision": "Bonne piste pour une PME ivoirienne qui cherche à devenir plus finançable, accéder à des marchés ou structurer son développement.",
    },
]


async def _hide_generic_vc4a(db) -> int:
    result = await db.execute(select(Device).where(Device.title.in_(VC4A_TOO_GENERIC)))
    devices = result.scalars().all()
    for device in devices:
        device.validation_status = "admin_only"
        device.user_quality_decision = "admin_only"
        device.user_quality_reasons = list(
            dict.fromkeys([*(device.user_quality_reasons or []), "vc4a_trop_global_hors_priorite_pays"])
        )
        device.updated_at = NOW
        device.last_verified_at = NOW
    return len(devices)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        hidden = await _hide_generic_vc4a(db)
        sources = {}
        for source_data in SOURCES:
            sources[source_data["name"]] = await upsert_source(db, source_data)

        counts = {"created": 0, "updated": 0}
        for device_data in DEVICES:
            status = await upsert_device(db, device_data, sources[device_data["source_name"]])
            counts[status] += 1

        await db.commit()
        print({"hidden_vc4a": hidden, "sources": len(sources), **counts})


if __name__ == "__main__":
    asyncio.run(main())
