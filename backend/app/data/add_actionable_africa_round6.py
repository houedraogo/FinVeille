"""Ajoute un lot d'opportunites Afrique de l'Ouest encore ouvertes et actionnables.

Les fiches sont curees manuellement pour eviter de publier des pages generiques ou
des appels expirés. Elles ciblent surtout Burkina Faso, Benin et Cote d'Ivoire.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

from app.database import AsyncSessionLocal
from app.data.add_actionable_africa_round3 import upsert_device, upsert_source


SOURCES: list[dict[str, Any]] = [
    {
        "name": "ComCashew e-MOVE - appels cajou",
        "organism": "GIZ / ComCashew / OEACP",
        "country": "Afrique",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "source_type": "programme_international",
        "level": 1,
        "url": "https://www.comcashew.org/financement-e-move",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "west_africa_cashew"},
        "notes": "Source officielle ComCashew/e-MOVE pour les jeunes agripreneurs de la chaine de valeur cajou.",
    },
    {
        "name": "FCI4Africa - Open Call 1",
        "organism": "FCI4Africa / Horizon Europe",
        "country": "Afrique",
        "region": "Afrique",
        "source_type": "programme_international",
        "level": 1,
        "url": "https://opencalls.fund/open-call/fci4africa-open-call-1",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "africa_food_systems"},
        "notes": "Source officielle OpenCalls pour FCI4Africa Open Call 1, financement innovation et systemes alimentaires.",
    },
    {
        "name": "OIF - industries culturelles appels 2026",
        "organism": "Organisation internationale de la Francophonie",
        "country": "Afrique",
        "region": "Afrique francophone",
        "source_type": "institution_internationale",
        "level": 1,
        "url": "https://www.francophonie.org/industries-culturelles-les-appels-a-projets-2026-8384",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "listing", "market": "francophone_creative_industries"},
        "notes": "Page officielle OIF regroupant les appels 2026 pour industries culturelles francophones.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "ComCashew e-MOVE - appels cajou",
        "title": "ComCashew e-MOVE - prix AgriCanvas pour jeunes agripreneurs du cajou",
        "organism": "GIZ / ComCashew / OEACP",
        "organism_type": "programme international",
        "country": "Afrique",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "international",
        "device_type": "concours",
        "aid_nature": "prix_entrepreneurial",
        "sectors": ["agriculture", "agroalimentaire", "cajou", "climat", "entrepreneuriat"],
        "beneficiaries": ["jeune entrepreneur", "agripreneur", "startup", "pme", "porteur projet"],
        "amount_min": Decimal("2000"),
        "amount_max": Decimal("2000"),
        "currency": "EUR",
        "open_date": date(2026, 3, 1),
        "close_date": date(2026, 5, 31),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://www.comcashew.org/financement-e-move",
        "source_raw": (
            "ComCashew/e-MOVE ouvre une periode de soumission de mars a mai 2026 pour des idees "
            "innovantes dans la chaine de valeur cajou. Les soumissions sont cloturees le 31 mai 2026. "
            "Les gagnants peuvent recevoir 2 000 EUR de financement direct ou des outils pratiques."
        ),
        "presentation": (
            "ComCashew/e-MOVE invite les jeunes agripreneurs de la chaine de valeur cajou a transformer "
            "leur idee en projet d'investissement plus solide et plus finançable."
        ),
        "eligibility": (
            "L'appel est ouvert aux jeunes agripreneurs ages de 18 ans et plus, bases dans un Etat membre "
            "de l'OEACP. Le Benin, le Burkina Faso et la Cote d'Ivoire sont pertinents pour cette opportunite "
            "car ils font partie des pays historiques d'intervention de ComCashew sur le cajou."
        ),
        "funding": (
            "Les laureats peuvent recevoir 2 000 EUR de financement direct, ou des outils pratiques comme "
            "un ordinateur portable ou un logiciel pour renforcer leur activite."
        ),
        "calendar": "Les soumissions sont ouvertes de mars a mai 2026, avec une date limite au 31 mai 2026.",
        "procedure": (
            "Suivre les cours e-MOVE utiles, completer l'AgriCanvas, puis soumettre l'idee via le formulaire "
            "officiel indique sur la page ComCashew."
        ),
        "checks": (
            "Confirmer l'eligibilite pays OEACP, la categorie exacte du projet cajou, le formulaire actif et "
            "la date limite avant soumission."
        ),
        "decision": (
            "Bonne opportunite courte pour un jeune entrepreneur agricole positionne sur la chaine de valeur "
            "cajou au Benin, Burkina Faso ou Cote d'Ivoire."
        ),
    },
    {
        "source_name": "FCI4Africa - Open Call 1",
        "title": "FCI4Africa Open Call 1 - jusqu'a 50 000 EUR pour l'innovation alimentaire",
        "organism": "FCI4Africa / Horizon Europe",
        "organism_type": "programme international",
        "country": "Afrique",
        "region": "Afrique",
        "zone": "Afrique",
        "geographic_scope": "continental",
        "device_type": "subvention",
        "aid_nature": "subvention_innovation",
        "sectors": ["agriculture", "agroalimentaire", "recherche", "technologie", "donnees"],
        "beneficiaries": ["startup", "pme", "universite", "centre de recherche", "acteur technologique"],
        "amount_min": Decimal("50000"),
        "amount_max": Decimal("50000"),
        "currency": "EUR",
        "open_date": date(2026, 4, 7),
        "close_date": date(2026, 6, 30),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://opencalls.fund/open-call/fci4africa-open-call-1",
        "source_raw": (
            "FCI4Africa Open Call 1 soutient des acteurs de recherche et technologie travaillant sur les "
            "systemes alimentaires africains. Jusqu'a huit sous-projets peuvent recevoir jusqu'a 50 000 EUR. "
            "Date limite: 30 juin 2026 a 17h00 CET."
        ),
        "presentation": (
            "FCI4Africa finance des projets qui testent, valident ou ameliorent des outils, donnees et concepts "
            "pour rendre les systemes alimentaires africains plus equitables, resilients et inclusifs."
        ),
        "eligibility": (
            "L'appel cible les universites, instituts de recherche, PME de R&D, startups innovantes et acteurs "
            "pluridisciplinaires. Les candidatures se font en porteur unique, sans consortium."
        ),
        "funding": (
            "L'enveloppe totale est de 400 000 EUR. Jusqu'a huit projets peuvent etre finances, avec un plafond "
            "de 50 000 EUR par sous-projet."
        ),
        "calendar": "Ouverture le 7 avril 2026. Date limite: 30 juin 2026 a 17h00 CET.",
        "procedure": (
            "Lire le guide candidat, verifier l'admissibilite technique, preparer le projet et deposer la "
            "candidature sur la plateforme OpenCalls."
        ),
        "checks": (
            "Verifier que le projet produit bien des resultats exploitables pour les systemes alimentaires "
            "africains, que le porteur peut candidater seul et que les donnees attendues sont preparables."
        ),
        "decision": (
            "A prioriser pour les startups, PME innovantes et structures de recherche qui travaillent sur "
            "l'agriculture, les donnees ou les technologies alimentaires en Afrique."
        ),
    },
    {
        "source_name": "OIF - industries culturelles appels 2026",
        "title": "OIF - soutien a la mobilite des artistes et biens culturels 2026",
        "organism": "Organisation internationale de la Francophonie",
        "organism_type": "institution internationale",
        "country": "Afrique",
        "region": "Afrique francophone",
        "zone": "Afrique",
        "geographic_scope": "international",
        "device_type": "subvention",
        "aid_nature": "mobilite_culturelle",
        "sectors": ["culture", "industries culturelles", "art", "spectacle vivant", "cooperation"],
        "beneficiaries": ["artiste", "collectif", "operateur culturel", "association", "entreprise culturelle"],
        "open_date": date(2026, 2, 23),
        "close_date": date(2026, 8, 31),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://www.francophonie.org/soutien-la-mobilite-des-artistes-et-circulation-des-biens-culturels-8385",
        "source_raw": (
            "L'OIF ouvre en 2026 un appel a projets de soutien a la mobilite des artistes et a la circulation "
            "des biens culturels. L'appel est ouvert du 23 fevrier au 31 aout 2026."
        ),
        "presentation": (
            "Cet appel OIF soutient des projets de mobilite artistique, de tournees, de rencontres "
            "professionnelles et de cooperation culturelle internationale dans l'espace francophone."
        ),
        "eligibility": (
            "La cible concerne les artistes professionnels, collectifs et operateurs culturels francophones "
            "ayant un projet de mobilite ou de circulation culturelle avec une dimension internationale."
        ),
        "funding": (
            "La source officielle confirme un soutien financier, mais le montant depend du reglement et du "
            "budget du projet. Il doit etre confirme dans les documents de candidature."
        ),
        "calendar": "Candidatures ouvertes du 23 fevrier au 31 aout 2026, avec selections et examens par sessions.",
        "procedure": (
            "Consulter la page officielle OIF, telecharger le reglement, verifier la categorie du projet puis "
            "deposer le dossier selon la procedure indiquee."
        ),
        "checks": (
            "Confirmer le montant mobilisable, les pays et disciplines admissibles, les justificatifs requis "
            "et les dates des sessions de selection."
        ),
        "decision": (
            "Bonne opportunite pour les acteurs culturels francophones du Benin, Burkina Faso ou Cote d'Ivoire "
            "qui ont un projet de mobilite ou de cooperation internationale."
        ),
    },
    {
        "source_name": "OIF - industries culturelles appels 2026",
        "title": "OIF Fonds Image de la Francophonie 2026 - cinema et fiction",
        "organism": "Organisation internationale de la Francophonie",
        "organism_type": "institution internationale",
        "country": "Afrique",
        "region": "Afrique francophone",
        "zone": "Afrique",
        "geographic_scope": "international",
        "device_type": "subvention",
        "aid_nature": "aide_audiovisuelle",
        "sectors": ["cinema", "audiovisuel", "culture", "fiction", "industries culturelles"],
        "beneficiaries": ["producteur", "realisateur", "entreprise culturelle", "association", "pme culturelle"],
        "open_date": date(2026, 3, 11),
        "close_date": date(2026, 6, 14),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://www.francophonie.org/fonds-images-de-la-francophonie-2026-cinema-fiction-session-1-8408",
        "source_raw": (
            "L'OIF lance une session 2026 du Fonds Image de la Francophonie pour le cinema-fiction. "
            "Le fonds soutient le developpement, la production ou la finition d'oeuvres audiovisuelles."
        ),
        "presentation": (
            "Le Fonds Image de la Francophonie soutient des projets de films, series ou oeuvres audiovisuelles "
            "francophones, notamment dans les pays a revenus faibles ou intermediaires."
        ),
        "eligibility": (
            "La cible principale concerne les professionnels du cinema et de l'audiovisuel de l'espace "
            "francophone: producteurs, realisateurs et structures porteuses de projets eligibles."
        ),
        "funding": (
            "Le dispositif apporte une aide financiere au developpement, a la production ou a la finition. "
            "Le montant depend de la commission, du type de projet et du reglement officiel."
        ),
        "calendar": "Session cinema-fiction 2026 avec date limite indiquee au 14 juin 2026.",
        "procedure": (
            "Lire le reglement OIF du Fonds Image, verifier la categorie de l'oeuvre et deposer le dossier "
            "via la procedure officielle."
        ),
        "checks": (
            "Confirmer la session exacte, les pieces artistiques et financieres attendues, le statut du porteur "
            "et les criteres pays avant depot."
        ),
        "decision": (
            "A regarder pour les producteurs et porteurs de projets audiovisuels francophones qui cherchent "
            "un financement professionnel, notamment en Afrique de l'Ouest."
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
