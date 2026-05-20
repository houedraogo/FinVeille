"""Ajoute des opportunites Afrique tres actionnables avec source officielle."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

from app.database import AsyncSessionLocal
from app.data.add_actionable_africa_round3 import upsert_device, upsert_source


SOURCES: list[dict[str, Any]] = [
    {
        "name": "Fonds canadien d'initiatives locales - Burkina Faso 2026",
        "organism": "Gouvernement du Canada / FCIL",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "ambassade",
        "level": 1,
        "url": "https://www.international.gc.ca/world-monde/funding-financement/cfli-fcil/burkina-faso.aspx?lang=fra",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "burkina_osc"},
        "notes": "Source officielle du Gouvernement du Canada pour le FCIL Burkina Faso 2026.",
    },
    {
        "name": "Invest for Jobs - IFE Cote d'Ivoire 2026",
        "organism": "Investing for Employment / KfW / BMZ",
        "country": "Côte d'Ivoire",
        "region": "Afrique de l'Ouest",
        "source_type": "programme_international",
        "level": 1,
        "url": "https://invest-for-jobs.com/en/news/ife-launches-call-for-proposals-in-c%C3%B4te-divoire-egypt-and-morocco",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "cote_ivoire_jobs"},
        "notes": "Source officielle IFE pour l'appel a propositions 2026 en Cote d'Ivoire.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "Fonds canadien d'initiatives locales - Burkina Faso 2026",
        "title": "Fonds canadien d'initiatives locales Burkina Faso 2026",
        "organism": "Gouvernement du Canada / FCIL",
        "organism_type": "ambassade",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "microfinancement",
        "sectors": ["gouvernance", "paix", "securite", "developpement local", "inclusion"],
        "beneficiaries": ["ong", "association", "organisation locale", "institution academique", "organisation internationale"],
        "amount_min": Decimal("45000"),
        "amount_max": Decimal("100000"),
        "currency": "CAD",
        "open_date": date(2026, 4, 28),
        "close_date": date(2026, 5, 22),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://www.international.gc.ca/world-monde/funding-financement/cfli-fcil/burkina-faso.aspx?lang=eng",
        "source_raw": "The Canada Fund for Local Initiatives Burkina Faso 2026 supports small-scale, high-impact projects. Deadline: May 22, 2026 at 23:59 GMT. Average contribution CAD 45,000 to 50,000, maximum CAD 100,000.",
        "presentation": "Le Fonds canadien d'initiatives locales finance des projets locaux a fort impact au Burkina Faso. L'appel 2026 vise des initiatives portees principalement par des organisations locales et alignees avec les priorites du Canada.",
        "eligibility": "Les beneficiaires eligibles incluent les ONG locales, organisations communautaires, institutions academiques locales, organisations internationales ou regionales travaillant avec des partenaires locaux.",
        "funding": "La contribution moyenne est de 45 000 a 50 000 CAD. Le plafond indique par la source officielle est de 100 000 CAD par projet eligible.",
        "calendar": "Date limite officielle: 22 mai 2026 a 23h59 GMT. Les projets doivent etre executes apres signature de l'accord et avant la date de fin indiquee par le programme.",
        "procedure": "Telecharger le formulaire partage par l'Ambassade du Canada au Burkina Faso, preparer le budget requis et envoyer le dossier a l'adresse officielle OUAGA.FCIL-CFLI@international.gc.ca.",
        "checks": "Verifier immediatement le formulaire officiel, la langue du dossier, les priorites thematiques retenues et l'heure limite avant soumission.",
        "decision": "Opportunite urgente et credible pour une ONG ou organisation locale burkinabe avec un projet concret, mesurable et rapidement executable.",
    },
    {
        "source_name": "Invest for Jobs - IFE Cote d'Ivoire 2026",
        "title": "Investing for Employment - subventions emploi Cote d'Ivoire 2026",
        "organism": "Investing for Employment / KfW / BMZ",
        "organism_type": "programme international",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "cofinancement_investissement",
        "sectors": ["emploi", "industrie", "agroalimentaire", "numerique", "formation", "services"],
        "beneficiaries": ["entreprise", "pme", "startup", "ong", "association", "universite", "chambre consulaire"],
        "amount_min": Decimal("800000"),
        "amount_max": Decimal("10000000"),
        "currency": "EUR",
        "open_date": date(2026, 4, 15),
        "close_date": date(2026, 6, 30),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://invest-for-jobs.com/en/news/ife-launches-call-for-proposals-in-c%C3%B4te-divoire-egypt-and-morocco",
        "source_raw": "Investing for Employment launched a 2026 call for proposals in Côte d'Ivoire. Applications can be submitted from 15 April to 30 June 2026. Grants range from EUR 800,000 to EUR 10 million.",
        "presentation": "Investing for Employment finance des projets d'investissement creant des emplois en Cote d'Ivoire. L'appel 2026 cible les projets matures, non demarres, capables de generer des emplois durables dans le secteur prive.",
        "eligibility": "Peuvent candidater des entreprises, organisations publiques, structures a but non lucratif, universites, chambres ou associations. Le projet doit creer des emplois dans le secteur prive et presenter une viabilite operationnelle et financiere.",
        "funding": "Les subventions vont de 800 000 EUR a 10 M EUR. Le taux de cofinancement varie selon la categorie du projet: jusqu'a 90 % pour certains projets non lucratifs et jusqu'a 25 % a 35 % pour des projets lucratifs.",
        "calendar": "Les candidatures sont ouvertes du 15 avril au 30 juin 2026. La procedure se deroule en deux etapes: note conceptuelle puis proposition complete pour les candidats preselectionnes.",
        "procedure": "Consulter la page officielle IFE, verifier les criteres dans le centre de telechargement, participer si besoin aux webinars, puis deposer la note conceptuelle via la plateforme indiquee.",
        "checks": "Confirmer la categorie du projet, le taux de cofinancement, la preuve de creation d'emplois, la maturite du projet et l'apport propre requis.",
        "decision": "Tres forte opportunite pour une entreprise ou organisation ivoirienne avec un projet d'investissement mature et une creation d'emplois mesurable.",
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        source_map = {}
        for source in SOURCES:
            source_map[source["name"]] = await upsert_source(db, source)
        created = 0
        updated = 0
        for device in DEVICES:
            action = await upsert_device(db, device, source_map[device["source_name"]])
            created += int(action == "created")
            updated += int(action == "updated")
        await db.commit()
    print({"sources": len(source_map), "created": created, "updated": updated})


if __name__ == "__main__":
    asyncio.run(main())
