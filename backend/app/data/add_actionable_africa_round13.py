from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.database import AsyncSessionLocal


NOW = datetime.now(timezone.utc)


SOURCES: list[dict[str, Any]] = [
    {
        "name": "BCEAO - Prix Abdoulaye FADIGA 2026",
        "organism": "BCEAO",
        "country": "Afrique de l'Ouest",
        "region": "UEMOA",
        "source_type": "institution_regionale",
        "level": 1,
        "url": "https://www.bceao.int/fr/content/prix-abdoulaye-fadiga-2026",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "pdf_manual", "market": "uemoa_recherche_financement"},
        "notes": "Affiche officielle BCEAO du Prix Abdoulaye FADIGA 2026, avec date limite et récompenses explicites.",
    },
    {
        "name": "FIN CULTURE Cote d'Ivoire - guichet ICC",
        "organism": "Ministere de la Culture et de la Francophonie",
        "country": "Côte d'Ivoire",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_public",
        "level": 1,
        "url": "https://culture.gouv.ci/projets/appel-a-projet-le-guichet-fin-culture-est-officiellement-ouvert/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 4,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "cote_ivoire_culture"},
        "notes": "Page officielle du ministère ivoirien de la Culture sur le guichet FIN CULTURE pour les industries culturelles et créatives.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "BCEAO - Prix Abdoulaye FADIGA 2026",
        "title": "BCEAO - Prix Abdoulaye FADIGA 2026 pour jeunes chercheurs UEMOA",
        "organism": "BCEAO",
        "organism_type": "institution régionale",
        "country": "Afrique de l'Ouest",
        "region": "UEMOA",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "concours",
        "aid_nature": "prix_recherche",
        "sectors": ["finance", "recherche", "economie", "innovation financière", "climat"],
        "beneficiaries": ["chercheur", "enseignant chercheur", "jeune chercheur", "équipe de recherche"],
        "amount_min": Decimal("5000000"),
        "amount_max": Decimal("10000000"),
        "currency": "XOF",
        "open_date": date(2026, 5, 20),
        "close_date": date(2026, 8, 31),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://www.bceao.int/fr/content/prix-abdoulaye-fadiga-2026",
        "source_raw": (
            "La BCEAO lance l'édition 2026 du Prix Abdoulaye FADIGA pour la promotion de la recherche économique. "
            "La date limite de soumission est le 31 août 2026. Le prix concerne les chercheurs ressortissants du Bénin, "
            "du Burkina Faso, de la Côte d'Ivoire, de la Guinée-Bissau, du Mali, du Niger, du Sénégal ou du Togo, âgés de "
            "45 ans au plus au 31 décembre 2026 et titulaires d'au moins Bac+5 en sciences économiques."
        ),
        "presentation": (
            "Le Prix Abdoulaye FADIGA 2026 récompense des travaux de recherche économique utiles aux économies de l'UEMOA, "
            "notamment sur la stabilité financière, le financement des économies, l'intégration régionale, le climat, "
            "l'inclusion financière ou la digitalisation."
        ),
        "eligibility": (
            "La candidature est ouverte aux chercheurs ou équipes de chercheurs en sciences économiques, ressortissants "
            "du Bénin, du Burkina Faso, de la Côte d'Ivoire, de la Guinée-Bissau, du Mali, du Niger, du Sénégal ou du Togo. "
            "Le candidat doit avoir 45 ans au plus au 31 décembre 2026 et justifier d'un diplôme d'au moins Bac+5."
        ),
        "funding": (
            "Le premier prix comprend une enveloppe de 10 millions FCFA, un séjour de recherche rémunéré d'un an à la BCEAO "
            "et la publication de l'étude primée. Un prix d'encouragement de 5 millions FCFA est également prévu."
        ),
        "calendar": "La date limite officielle de soumission est fixée au 31 août 2026.",
        "procedure": (
            "Préparer la fiche de candidature, l'étude complète, le résumé de 500 mots, l'étude originale, les bases de données "
            "ou programmes utilisés, le CV, la pièce d'identité et la charte anti-plagiat, puis envoyer le dossier à l'adresse "
            "indiquée par la BCEAO."
        ),
        "checks": (
            "Vérifier sur le site de la BCEAO les documents officiels à télécharger, l'adresse de dépôt, les formats acceptés "
            "et les exigences linguistiques avant soumission."
        ),
        "decision": (
            "Bonne opportunité pour un jeune chercheur ou une équipe de recherche d'Afrique de l'Ouest travaillant sur le "
            "financement, l'inclusion financière, la stabilité économique ou les politiques publiques."
        ),
    },
    {
        "source_name": "FIN CULTURE Cote d'Ivoire - guichet ICC",
        "title": "FIN CULTURE Côte d'Ivoire - prêts pour industries culturelles et créatives",
        "organism": "Ministère de la Culture et de la Francophonie",
        "organism_type": "ministère",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "pret_culture",
        "sectors": ["culture", "industries créatives", "entrepreneuriat", "jeunesse", "artisanat"],
        "beneficiaries": ["entrepreneur", "jeune entrepreneur", "pme", "acteur culturel", "porteur projet"],
        "amount_min": Decimal("1000000"),
        "amount_max": Decimal("20000000"),
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://culture.gouv.ci/projets/appel-a-projet-le-guichet-fin-culture-est-officiellement-ouvert/",
        "source_raw": (
            "Le Ministère de la Culture et de la Francophonie indique que le guichet FIN CULTURE rouvre pour les acteurs des "
            "industries culturelles et créatives en Côte d'Ivoire, avec des financements sous forme de prêts allant de 1 à "
            "20 millions FCFA. La page renvoie vers la plateforme de l'Agence Emploi Jeunes pour faire une demande."
        ),
        "presentation": (
            "FIN CULTURE est un guichet destiné aux acteurs des industries culturelles et créatives en Côte d'Ivoire. Il vise "
            "à financer des projets culturels, créatifs ou entrepreneuriaux portés notamment par des jeunes ivoiriens."
        ),
        "eligibility": (
            "La cible principale concerne les acteurs des industries culturelles et créatives, les jeunes entrepreneurs, PME, "
            "porteurs de projets culturels ou structures créatives en Côte d'Ivoire."
        ),
        "funding": (
            "Le guichet annonce des prêts de 1 à 20 millions FCFA. Les conditions de remboursement, garanties, pièces exigées "
            "et critères de sélection doivent être confirmés sur la plateforme de demande."
        ),
        "calendar": (
            "La page officielle ne donne pas une date limite exploitable dans le texte principal. La fiche est donc suivie "
            "comme guichet à vérifier avant candidature."
        ),
        "procedure": (
            "Consulter la page officielle, ouvrir le lien de demande vers la plateforme de l'Agence Emploi Jeunes, puis vérifier "
            "si le formulaire est toujours actif avant de préparer le dossier."
        ),
        "checks": (
            "Confirmer que le guichet est encore ouvert, que le lien de dépôt fonctionne, les conditions du prêt, les garanties "
            "éventuelles et la liste des pièces demandées."
        ),
        "decision": (
            "Piste intéressante pour les entrepreneurs culturels ivoiriens, mais à vérifier avant de la prioriser car la source "
            "ne publie pas une date limite claire."
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
