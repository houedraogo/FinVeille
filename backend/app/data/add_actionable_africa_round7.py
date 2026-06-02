"""Ajoute un lot prudent de guichets actionnables Afrique de l'Ouest.

Ce round privilegie les sources candidatables et recurrentes plutot que les
appels ponctuels fragiles. Les fiches doivent rester utiles cote utilisateur
sans promettre une fenetre de candidature quand la source ne publie pas de date
fiable.
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
        "name": "AEJ Cote d'Ivoire - plateforme financement jeunes entrepreneurs",
        "organism": "Agence Emploi Jeunes Cote d'Ivoire",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://agenceemploijeunes.ci/entrepreneuriat",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "cote_ivoire_jeunesse"},
        "notes": "Plateforme officielle AEJ pour financement, formation et accompagnement des jeunes entrepreneurs ivoiriens.",
    },
    {
        "name": "FONSTI Cote d'Ivoire - guichets innovation et entrepreneuriat",
        "organism": "Fonds pour la Science, la Technologie et l'Innovation",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "source_type": "fonds_public",
        "level": 1,
        "url": "https://fonsti.org/appel-a-projets/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "cote_ivoire_innovation"},
        "notes": "Page officielle FONSTI avec formulaires de soumission, notamment Innovation et Entrepreneuriat.",
    },
    {
        "name": "Orange Fab Burkina Faso - acceleration startups digitales",
        "organism": "Orange Digital Center Burkina Faso",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "incubateur",
        "level": 1,
        "url": "https://www.orange.bf/fr/odc/programme-orange-fab.html",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 4,
        "category": "private",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "burkina_startups"},
        "notes": "Programme d'acceleration Orange Fab Burkina Faso. La page officielle peut afficher une saison passee; a surveiller pour la prochaine fenetre.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "AEJ Cote d'Ivoire - plateforme financement jeunes entrepreneurs",
        "title": "AEJ Côte d'Ivoire - financement et accompagnement des jeunes entrepreneurs",
        "organism": "Agence Emploi Jeunes Cote d'Ivoire",
        "organism_type": "agence nationale",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "financement_entrepreneuriat",
        "sectors": ["entrepreneuriat", "jeunesse", "formation", "pme", "emploi"],
        "beneficiaries": ["jeune entrepreneur", "porteur projet", "startup", "pme", "entrepreneur"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://agenceemploijeunes.ci/entrepreneuriat",
        "source_raw": (
            "La plateforme entrepreneuriat de l'Agence Emploi Jeunes presente des parcours pour les jeunes "
            "promoteurs: formation, accompagnement, maturation du projet et mise a disposition du financement."
        ),
        "presentation": (
            "L'Agence Emploi Jeunes est une porte d'entree publique pour les jeunes ivoiriens qui veulent "
            "structurer un projet entrepreneurial, obtenir un accompagnement et acceder a un financement adapte."
        ),
        "eligibility": (
            "Cette piste cible surtout les jeunes porteurs de projets, promoteurs, entrepreneurs et petites "
            "entreprises en Cote d'Ivoire. Le niveau de maturite attendu depend du parcours propose par l'AEJ."
        ),
        "funding": (
            "L'appui peut combiner formation, coaching, accompagnement technique et facilitation du financement. "
            "Le montant depend du programme et du niveau de maturite du projet."
        ),
        "calendar": (
            "Guichet recurrent: les sessions et dispositifs sont publies par l'AEJ selon les programmes actifs."
        ),
        "procedure": (
            "Consulter la plateforme officielle AEJ, identifier le parcours entrepreneuriat pertinent, creer un "
            "compte si necessaire et suivre les etapes de depot ou d'inscription."
        ),
        "checks": (
            "Confirmer la session ouverte, l'age ou le profil requis, les pieces demandees, le montant mobilisable "
            "et les conditions de remboursement ou de suivi."
        ),
        "decision": (
            "Bonne opportunite de base pour un jeune entrepreneur ivoirien qui cherche un accompagnement public "
            "et une porte d'entree vers le financement."
        ),
    },
    {
        "source_name": "FONSTI Cote d'Ivoire - guichets innovation et entrepreneuriat",
        "title": "FONSTI Côte d'Ivoire - financement innovation et entrepreneuriat",
        "organism": "Fonds pour la Science, la Technologie et l'Innovation",
        "organism_type": "fonds public",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "innovation_entrepreneuriat",
        "sectors": ["innovation", "recherche", "technologie", "entrepreneuriat", "industrie"],
        "beneficiaries": ["chercheur", "startup", "pme", "universite", "centre de recherche", "entrepreneur"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://fonsti.org/appel-a-projets/",
        "source_raw": (
            "Le FONSTI publie des formulaires de soumission pour plusieurs categories, dont Innovation et "
            "Entrepreneuriat, Recherche appliquee, Developpement experimental et Infrastructures."
        ),
        "presentation": (
            "Le FONSTI finance et accompagne des projets de science, technologie, innovation et entrepreneuriat "
            "en Cote d'Ivoire. La page officielle permet de postuler par categorie de projet."
        ),
        "eligibility": (
            "La source concerne des porteurs ivoiriens ou structures actives en Cote d'Ivoire: chercheurs, "
            "universites, startups, PME innovantes, laboratoires, centres techniques et entrepreneurs."
        ),
        "funding": (
            "L'appui porte sur le financement de projets d'innovation, de recherche appliquee, de developpement "
            "experimental ou d'infrastructures. Les montants sont a confirmer dans chaque appel ou formulaire."
        ),
        "calendar": (
            "Guichet recurrent: les appels en cours et formulaires de soumission sont geres sur la plateforme FONSTI."
        ),
        "procedure": (
            "Choisir la categorie pertinente sur la page officielle, creer un compte si necessaire, puis remplir "
            "le formulaire de soumission avec le projet et les justificatifs demandes."
        ),
        "checks": (
            "Verifier la categorie exacte, la date d'ouverture, les criteres d'evaluation, le budget admissible "
            "et les documents scientifiques ou financiers a joindre."
        ),
        "decision": (
            "A prioriser pour une startup, PME innovante ou equipe de recherche ivoirienne qui porte un projet "
            "technologique ou entrepreneurial structurant."
        ),
    },
    {
        "source_name": "Orange Fab Burkina Faso - acceleration startups digitales",
        "title": "Orange Fab Burkina Faso - accélération de startups digitales",
        "organism": "Orange Digital Center Burkina Faso",
        "organism_type": "incubateur",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "acceleration_startup",
        "sectors": ["numerique", "fintech", "agriculture", "economie circulaire", "intelligence artificielle"],
        "beneficiaries": ["startup", "entrepreneur", "pme innovante", "porteur projet"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.orange.bf/fr/odc/programme-orange-fab.html",
        "source_raw": (
            "Orange Fab Burkina Faso accompagne les startups digitales pendant 6 a 9 mois avec diagnostic, "
            "mentorat, acces marche, soutien a la levee de fonds et reseau international Orange."
        ),
        "presentation": (
            "Orange Fab Burkina Faso est un programme d'acceleration pour startups digitales qui veulent "
            "structurer leur produit, acceder au marche burkinabe et se connecter au reseau Orange."
        ),
        "eligibility": (
            "Le programme cible des startups innovantes avec une solution tech, une synergie possible avec "
            "Orange et une disponibilite pour suivre l'accompagnement. Les criteres exacts varient par saison."
        ),
        "funding": (
            "L'appui principal porte sur le mentorat, l'acces marche, les formations, le reseau et le soutien a "
            "la levee de fonds. La source ne garantit pas une subvention directe."
        ),
        "calendar": (
            "Programme recurrent par saison. La page officielle affiche parfois une saison precedente; il faut "
            "verifier la prochaine fenetre avant de candidater."
        ),
        "procedure": (
            "Surveiller la page Orange Fab, telecharger le modele de dossier lorsque la saison est ouverte, puis "
            "soumettre la presentation via le formulaire officiel."
        ),
        "checks": (
            "Confirmer que la saison en cours est ouverte, la date limite, les secteurs prioritaires et les "
            "documents demandes avant toute candidature."
        ),
        "decision": (
            "Bonne piste de veille pour une startup digitale au Burkina Faso, surtout si elle cherche mentorat, "
            "acces marche et preparation a la levee de fonds."
        ),
    },
    {
        "source_name": "Seme City - RISE 2 Benin",
        "title": "RISE 2 Bénin - accélération et financement des PME et startups",
        "organism": "Seme City / ADPME / Gouvernement du Benin",
        "organism_type": "programme national",
        "country": "Bénin",
        "region": "Bénin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "acceleration_financement",
        "sectors": ["agroalimentaire", "numerique", "industrie", "services", "economie verte", "culture"],
        "beneficiaries": ["pme", "startup", "entreprise", "entrepreneur"],
        "amount_min": Decimal("7500000"),
        "amount_max": Decimal("28000000"),
        "currency": "XOF",
        "open_date": date(2026, 5, 8),
        "close_date": date(2026, 6, 7),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://semecity.bj/programmes/rise/",
        "source_raw": (
            "RISE edition 2 est ouvert jusqu'au 7 juin 2026 pour les PME et startups beninoises. Les entreprises "
            "retenues peuvent obtenir jusqu'a 7,5 millions FCFA ou 28 millions FCFA selon leur categorie, avec "
            "formation, coaching et mise en reseau."
        ),
        "presentation": (
            "RISE 2 est un programme d'acceleration du Gouvernement du Benin, de Seme City et de l'ADPME pour "
            "aider les PME et startups beninoises a fort potentiel a passer un cap de croissance."
        ),
        "eligibility": (
            "Le programme cible deux profils: jeunes entreprises formalisees en phase d'amorcage et PME a fort "
            "potentiel creees depuis au moins un an. Les secteurs prioritaires incluent l'agroalimentaire, le "
            "numerique, les services, l'economie verte, le climat, l'artisanat et les industries culturelles."
        ),
        "funding": (
            "L'appui peut atteindre 7,5 millions FCFA ou 28 millions FCFA selon la categorie, avec un "
            "accompagnement personnalise, des formations, du coaching et de la mise en reseau."
        ),
        "calendar": "Les candidatures sont ouvertes jusqu'au 7 juin 2026.",
        "procedure": (
            "Consulter la page officielle RISE, verifier la categorie de candidature, preparer les informations "
            "financieres et deposer le dossier via la plateforme indiquee."
        ),
        "checks": (
            "Verifier la categorie exacte, le chiffre d'affaires admissible, les pieces demandees, les conditions "
            "de cofinancement et la date limite avant depot."
        ),
        "decision": (
            "Tres bonne opportunite pour une PME ou startup beninoise qui veut combiner financement, coaching "
            "et mise en reseau pour accelerer sa croissance."
        ),
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        sources = {}
        for source_data in SOURCES:
            sources[source_data["name"]] = await upsert_source(db, source_data)

        # RISE 2 existe deja dans un round precedent; on reutilise sa source.
        if "Seme City - RISE 2 Benin" not in sources:
            result_source = await upsert_source(
                db,
                {
                    "name": "Seme City - RISE 2 Benin",
                    "organism": "Seme City / ADPME / Gouvernement du Benin",
                    "country": "Bénin",
                    "region": "Afrique de l'Ouest",
                    "source_type": "programme_national",
                    "level": 1,
                    "url": "https://semecity.bj/programmes/rise/",
                    "collection_mode": "manual",
                    "check_frequency": "weekly",
                    "reliability": 5,
                    "category": "public",
                    "is_active": True,
                    "config": {"source_kind": "single_program_page", "market": "benin_pme"},
                    "notes": "Source officielle Seme City pour RISE 2.",
                },
            )
            sources["Seme City - RISE 2 Benin"] = result_source

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
