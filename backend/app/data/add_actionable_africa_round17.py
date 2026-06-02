from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.database import AsyncSessionLocal


NOW = datetime.now(timezone.utc)


SOURCES: list[dict[str, Any]] = [
    {
        "name": "FONAFI Burkina Faso - finance inclusive",
        "organism": "Fonds National de la Finance Inclusive",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "fonds_public",
        "level": 1,
        "url": "https://www.fonafi-bf.org/fonafi-le-fonds-national-de-la-finance-inclusive/",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "burkina_finance_inclusive"},
        "notes": "Fonds public burkinabe de finance inclusive, lignes de credit, fonds de garantie et facilitation via les PSF/SFD.",
    },
    {
        "name": "Fonds Pananetugri - jeunes femmes Afrique de l'Ouest",
        "organism": "Initiative Pananetugri pour le Bien-être de la Femme",
        "country": "Afrique de l'Ouest",
        "region": "Afrique de l'Ouest",
        "source_type": "fonds_ong",
        "level": 2,
        "url": "https://www.ongipbf.org/fonds-pananetugri/",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 4,
        "category": "ngo",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "west_africa_young_women_orgs"},
        "notes": "Fonds flexible pour groupes et organisations de jeunes filles et jeunes femmes en Afrique de l'Ouest francophone.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "FONAFI Burkina Faso - finance inclusive",
        "title": "FONAFI Burkina Faso - lignes de crédit et garanties pour finance inclusive",
        "organism": "Fonds National de la Finance Inclusive",
        "organism_type": "fonds public",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "garantie",
        "aid_nature": "finance_inclusive",
        "sectors": ["agriculture", "entrepreneuriat", "finance inclusive", "microfinance", "commerce", "elevage"],
        "beneficiaries": ["entrepreneur", "exploitant agricole", "femme entrepreneure", "jeune entrepreneur", "tpe", "cooperative"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.fonafi-bf.org/fonafi-le-fonds-national-de-la-finance-inclusive/",
        "source_raw": (
            "Le FONAFI est un outil de facilitation des financements de projets productifs au Burkina Faso. "
            "Il intervient par lignes de crédit, fonds de garantie et fonds de facilitation, en lien avec les prestataires de services financiers, systèmes financiers décentralisés et autres institutions financières. "
            "La source indique que les lignes de crédit visent notamment les personnes à faibles revenus, exploitants agricoles familiaux et entrepreneurs agricoles."
        ),
        "presentation": (
            "Le FONAFI facilite l'accès au crédit et aux garanties pour des publics qui ont souvent du mal à accéder au financement classique au Burkina Faso."
        ),
        "eligibility": (
            "La cible concerne les personnes à faibles revenus, exploitants agricoles familiaux, entrepreneurs agricoles, petits porteurs d'activités productives et bénéficiaires servis par des prestataires de services financiers partenaires."
        ),
        "funding": (
            "Le FONAFI agit surtout via des lignes de crédit, des fonds de garantie et des mécanismes de facilitation à travers les institutions financières partenaires. Les montants et produits exacts dépendent du partenaire financier et du guichet mobilisé."
        ),
        "calendar": (
            "Dispositif permanent ou récurrent. Les opportunités concrètes dépendent des partenaires financiers, appels ou guichets actifs au moment de la demande."
        ),
        "procedure": (
            "Identifier un prestataire de services financiers partenaire, vérifier le guichet adapté au projet, puis préparer un dossier de demande de crédit ou d'appui selon les exigences du partenaire."
        ),
        "checks": (
            "Confirmer le partenaire financier disponible, le guichet actif, les conditions d'accès, les garanties demandées, les zones couvertes et les montants accessibles avant d'orienter un bénéficiaire."
        ),
        "decision": (
            "Bonne piste pour les entrepreneurs agricoles, petits porteurs d'activités et publics vulnérables qui cherchent un crédit ou une garantie adaptée au Burkina Faso."
        ),
    },
    {
        "source_name": "Fonds Pananetugri - jeunes femmes Afrique de l'Ouest",
        "title": "Fonds Pananetugri - subventions pour organisations de jeunes femmes",
        "organism": "Initiative Pananetugri pour le Bien-être de la Femme",
        "organism_type": "organisation féministe",
        "country": "Afrique de l'Ouest",
        "region": "Afrique de l'Ouest",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "subvention",
        "aid_nature": "subvention_organisation_feministe",
        "sectors": ["genre", "droits des femmes", "jeunesse", "association", "impact social", "leadership"],
        "beneficiaries": ["association", "ong", "femme entrepreneure", "jeune femme", "organisation communautaire"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.ongipbf.org/fonds-pananetugri/",
        "source_raw": (
            "Le Fonds Pananetugri est un fonds flexible destiné aux groupes et organisations dirigés par des jeunes filles et jeunes femmes en Afrique de l'Ouest francophone. "
            "La source officielle indique que le fonds soutient le développement organisationnel, institutionnel et des actions innovantes en faveur des droits des jeunes filles et jeunes femmes. "
            "Les pays mentionnés incluent notamment le Bénin, le Burkina Faso et la Côte d'Ivoire."
        ),
        "presentation": (
            "Le Fonds Pananetugri soutient des organisations ou groupes de jeunes filles et jeunes femmes qui portent des actions sociales, féministes ou communautaires en Afrique de l'Ouest francophone."
        ),
        "eligibility": (
            "Le fonds cible des groupes ou organisations locales/nationales dirigés par des jeunes filles et jeunes femmes de moins de 40 ans, avec plus de 75% de jeunes filles et jeunes femmes dans l'organisation."
        ),
        "funding": (
            "Le fonds peut octroyer des subventions flexibles pour le développement organisationnel, institutionnel et des actions innovantes. Les montants, périodes d'appel et formulaires doivent être confirmés sur la page officielle."
        ),
        "calendar": (
            "Dispositif à suivre comme fonds récurrent. La page officielle conserve des informations de référence, mais la fenêtre active de dépôt doit être vérifiée avant candidature."
        ),
        "procedure": (
            "Consulter la page officielle, vérifier si un appel à propositions est ouvert, lire les lignes directrices, puis préparer la proposition et les pièces demandées dans le format indiqué."
        ),
        "checks": (
            "Confirmer l'ouverture actuelle de l'appel, le formulaire à utiliser, les pays éligibles, les montants disponibles, les documents requis et l'adresse officielle de soumission."
        ),
        "decision": (
            "Piste pertinente pour une association ou organisation portée par des jeunes femmes au Bénin, Burkina Faso, Côte d'Ivoire ou dans un autre pays francophone d'Afrique de l'Ouest."
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
