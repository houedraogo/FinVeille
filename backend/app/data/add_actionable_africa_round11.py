from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.database import AsyncSessionLocal


NOW = datetime.now(timezone.utc)


SOURCES: list[dict[str, Any]] = [
    {
        "name": "WEDAF Benin - entrepreneuriat feminin et financement",
        "organism": "Ministère des PME et de la Promotion de l'Emploi / Banque mondiale",
        "country": "Bénin",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_public",
        "level": 1,
        "url": "https://pmepe.gouv.bj/article/81/projet-developpement-entrepreneuriat-feminin-acces-financement-wedaf",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "benin_femmes_pme"},
        "notes": "Programme public béninois d'entrepreneuriat féminin et d'accès au financement, appuyé par la Banque mondiale.",
    },
    {
        "name": "PAEFA Benin - entrepreneuriat feminin",
        "organism": "APEFE",
        "country": "Bénin",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_international",
        "level": 1,
        "url": "https://www.apefe.org/programme/entrepreneuriat-feminin/",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 4,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "benin_femmes"},
        "notes": "Programme d'appui à l'entrepreneuriat féminin au Bénin: diagnostic, plans d'affaires, formation, équipement et financement.",
    },
    {
        "name": "BIIC Avec Elles Benin - financement femmes entrepreneures",
        "organism": "BIIC",
        "country": "Bénin",
        "region": "Afrique de l'Ouest",
        "source_type": "banque",
        "level": 1,
        "url": "https://www.biic-bank.com/fr/levee-de-fonds.html",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 4,
        "category": "private",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "benin_femmes_pme"},
        "notes": "Programme BIIC Avec Elles pour femmes entrepreneures béninoises, combinant financement et accompagnement.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "WEDAF Benin - entrepreneuriat feminin et financement",
        "title": "WEDAF Bénin - entrepreneuriat féminin et accès au financement",
        "organism": "Ministère des PME et de la Promotion de l'Emploi / Banque mondiale",
        "organism_type": "programme public",
        "country": "Bénin",
        "region": "Bénin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "acces_financement",
        "sectors": ["entrepreneuriat", "pme", "finance", "femmes", "formalisation"],
        "beneficiaries": ["femme entrepreneure", "pme", "tpe", "entrepreneur", "entreprise informelle"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://pmepe.gouv.bj/article/81/projet-developpement-entrepreneuriat-feminin-acces-financement-wedaf",
        "source_raw": "Le WEDAF est un projet de développement de l'entrepreneuriat féminin et d'accès au financement au Bénin. Il vise à accompagner les femmes entrepreneures, améliorer l'accès aux services financiers et renforcer l'écosystème d'appui aux PME féminines.",
        "presentation": "WEDAF est un programme structurant pour développer l'entrepreneuriat féminin au Bénin. Il vise à améliorer l'accès des femmes entrepreneures au financement, à l'accompagnement et aux services utiles pour développer leur activité.",
        "eligibility": "La cible principale concerne les femmes entrepreneures, les TPE/PME dirigées par des femmes et certaines entrepreneures du secteur informel pouvant évoluer vers une activité plus structurée.",
        "funding": "L'appui porte sur l'accès au financement, l'accompagnement entrepreneurial, la structuration des mécanismes d'appui et le renforcement des dispositifs existants. Les guichets, tickets et modalités pratiques doivent être confirmés sur les canaux officiels.",
        "calendar": "Programme structurant à suivre. Les appels, guichets ou mécanismes opérationnels peuvent être publiés progressivement par les institutions partenaires.",
        "procedure": "Suivre les communications du ministère, de l'ADPME, des institutions financières partenaires et des guichets associés pour identifier les phases opérationnelles ouvertes.",
        "checks": "Confirmer le guichet actif, les critères exacts, les documents demandés et la forme de financement avant d'engager une démarche.",
        "decision": "Très bonne piste de veille pour les femmes entrepreneures au Bénin, surtout pour anticiper les futurs guichets d'accès au financement.",
    },
    {
        "source_name": "PAEFA Benin - entrepreneuriat feminin",
        "title": "PAEFA Bénin - accompagnement et financement des entreprises féminines",
        "organism": "APEFE",
        "organism_type": "programme international",
        "country": "Bénin",
        "region": "Bénin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "appui_entrepreneuriat_feminin",
        "sectors": ["entrepreneuriat", "femmes", "pme", "formation", "finance"],
        "beneficiaries": ["femme entrepreneure", "pme", "tpe", "entrepreneur", "entreprise"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.apefe.org/programme/entrepreneuriat-feminin/",
        "source_raw": "Le PAEFA accompagne les entreprises féminines au Bénin avec des diagnostics d'entreprise, de l'aide à la création de plans d'affaires, des formations en gestion, du soutien en équipement et en financement, ainsi que la participation à des foires et événements.",
        "presentation": "PAEFA accompagne les femmes entrepreneures béninoises pour renforcer leur entreprise, clarifier leur plan d'affaires et améliorer leur accès aux ressources nécessaires à la croissance.",
        "eligibility": "La cible concerne les femmes entrepreneures et entreprises féminines au Bénin. Les critères précis dépendent des cohortes, zones ou activités ouvertes par le programme.",
        "funding": "L'appui peut inclure diagnostic, formation en gestion, plan d'affaires, accompagnement, soutien en équipement, facilitation du financement et participation à des foires ou événements.",
        "calendar": "Programme récurrent: les sessions et modalités doivent être suivies via la page officielle ou les communications de l'APEFE.",
        "procedure": "Consulter la page officielle, identifier les contacts ou appels en cours, puis préparer les informations sur l'activité, les besoins d'accompagnement et le plan de croissance.",
        "checks": "Vérifier la disponibilité d'une cohorte, les zones couvertes, la nature exacte du financement et les documents exigés.",
        "decision": "Bonne piste pour une femme entrepreneure béninoise qui cherche à renforcer son activité avant ou pendant une recherche de financement.",
    },
    {
        "source_name": "BIIC Avec Elles Benin - financement femmes entrepreneures",
        "title": "BIIC Avec Elles Bénin - financement et accompagnement des femmes entrepreneures",
        "organism": "BIIC",
        "organism_type": "banque",
        "country": "Bénin",
        "region": "Bénin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "credit_et_accompagnement",
        "sectors": ["entrepreneuriat", "femmes", "pme", "finance", "commerce"],
        "beneficiaries": ["femme entrepreneure", "pme", "tpe", "entrepreneur", "entreprise"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.biic-bank.com/fr/levee-de-fonds.html",
        "source_raw": "BIIC Avec Elles est un programme de la Banque Internationale pour l'Industrie et le Commerce visant à soutenir les femmes entrepreneures au Bénin, en combinant solutions de financement et accompagnement technique.",
        "presentation": "BIIC Avec Elles est une piste de financement bancaire et d'accompagnement pour les femmes entrepreneures béninoises. Le programme vise à proposer des solutions adaptées au cycle d'activité et à la maturité des projets.",
        "eligibility": "La cible principale concerne les femmes entrepreneures et entreprises portées par des femmes au Bénin. L'éligibilité dépend du profil de l'entreprise, de la maturité du projet, du secteur et de la capacité de remboursement.",
        "funding": "L'appui peut combiner crédit, accompagnement, orientation financière et suivi. Les montants, garanties, taux et durées doivent être confirmés directement avec la BIIC.",
        "calendar": "Programme récurrent ou renouvelé par cohortes. Les fenêtres exactes et sessions doivent être vérifiées sur la page officielle ou auprès de la banque.",
        "procedure": "Consulter la page BIIC, contacter l'agence ou le programme BIIC Avec Elles, puis préparer les pièces de l'entreprise, le besoin de financement et les justificatifs demandés.",
        "checks": "Confirmer la cohorte ouverte, les conditions bancaires, les garanties, les frais et la liste des documents avant de déposer une demande.",
        "decision": "Piste intéressante pour une femme entrepreneure au Bénin qui recherche un financement bancaire accompagné plutôt qu'une subvention.",
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
