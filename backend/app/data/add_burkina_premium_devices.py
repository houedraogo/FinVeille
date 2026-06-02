"""Ajoute des fiches publiques premium issues des nouvelles sources Burkina.

Principe: publier seulement ce qui est actionnable ou utile a surveiller,
avec un statut explicite. Les appels sans fenetre confirmee restent en
"recurring" et "publish_with_caution", jamais en faux "open".
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

from app.database import AsyncSessionLocal
from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.data.add_burkina_actionable_sources import SOURCES as BURKINA_SOURCES


SOURCES: list[dict[str, Any]] = [
    {
        "name": "BCEAO - Prix Abdoulaye FADIGA 2026",
        "organism": "Banque Centrale des Etats de l'Afrique de l'Ouest",
        "country": "Afrique de l'Ouest",
        "region": "UEMOA",
        "source_type": "institution_regionale",
        "level": 1,
        "url": "https://www.bceao.int/fr/content/prix-abdoulaye-fadiga-2026",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {
            "source_kind": "single_program_page",
            "publication_policy": "manual_review_required",
            "target_countries": ["Burkina Faso", "Bénin", "Côte d'Ivoire"],
            "target_profiles": ["chercheur", "université", "consultant"],
            "focus": ["recherche", "economie", "finance", "prix"],
        },
        "notes": "Source officielle BCEAO pour l'edition 2026 du Prix Abdoulaye FADIGA.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "BCEAO - Prix Abdoulaye FADIGA 2026",
        "title": "BCEAO - Prix Abdoulaye FADIGA 2026 pour jeunes chercheurs UEMOA",
        "organism": "Banque Centrale des Etats de l'Afrique de l'Ouest",
        "organism_type": "institution régionale",
        "country": "Afrique de l'Ouest",
        "region": "Burkina Faso, Bénin, Côte d'Ivoire, UEMOA",
        "zone": "UEMOA",
        "geographic_scope": "regional",
        "device_type": "concours",
        "aid_nature": "prix_recherche",
        "sectors": ["recherche", "economie", "finance", "statistique", "innovation"],
        "beneficiaries": ["chercheur", "équipe de recherche", "université", "consultant"],
        "amount_min": Decimal("10000000"),
        "amount_max": Decimal("10000000"),
        "currency": "XOF",
        "open_date": date(2026, 4, 20),
        "close_date": date(2026, 8, 31),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://www.bceao.int/fr/content/prix-abdoulaye-fadiga-2026",
        "source_raw": (
            "La BCEAO lance l'edition 2026 du Prix Abdoulaye FADIGA pour la promotion de la "
            "recherche economique au sein de l'UEMOA. Date limite: 31 aout 2026. Le laureat "
            "beneficie d'une enveloppe financiere de 10 000 000 FCFA."
        ),
        "presentation": (
            "Le Prix Abdoulaye FADIGA recompense des travaux de recherche economique utiles aux economies "
            "de l'UEMOA. Il peut interesser les jeunes chercheurs du Burkina Faso, du Benin et de la "
            "Cote d'Ivoire travaillant sur l'economie, la finance, les statistiques ou les politiques publiques."
        ),
        "eligibility": (
            "L'appel s'adresse aux chercheurs ou equipes de chercheurs en sciences economiques ou disciplines "
            "connexes, ressortissants d'un Etat membre de l'UEMOA. Les candidats doivent avoir 45 ans au plus "
            "au 31 decembre 2026 et justifier au minimum d'un niveau Bac+5."
        ),
        "funding": (
            "Le laureat reçoit une enveloppe financiere de 10 000 000 FCFA, ainsi qu'une reconnaissance "
            "institutionnelle regionale par la BCEAO."
        ),
        "calendar": "La date limite de soumission est fixee au 31 aout 2026.",
        "procedure": (
            "Preparer le dossier selon les formulaires BCEAO et l'envoyer a l'adresse officielle "
            "prixabdoulayefadiga@bceao.int avant la date limite."
        ),
        "checks": (
            "Verifier les documents de candidature, l'age limite, le niveau academique, la thematique de "
            "recherche et les exigences contre le plagiat sur la page officielle BCEAO."
        ),
        "decision": (
            "Tres bonne opportunite pour un jeune chercheur UEMOA qui dispose deja d'un travail solide en "
            "economie, finance, statistiques ou politiques publiques."
        ),
    },
    {
        "source_name": "FBDES Burkina Faso - Guichet Teelba",
        "title": "FBDES - Guichet TEELBA pour la résilience économique au Burkina Faso",
        "organism": "Fonds Burkinabe de Developpement Economique et Social",
        "organism_type": "fonds public",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "subvention_et_credit",
        "sectors": ["entrepreneuriat", "pme", "résilience", "économie locale", "inclusion"],
        "beneficiaries": ["association", "groupement", "coopérative", "tpe", "pme"],
        "amount_min": Decimal("1000000"),
        "amount_max": Decimal("10000000"),
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Guichet public à surveiller : les formulaires 2025 sont publiés, les prochaines fenêtres doivent être confirmées sur FBDES.",
        "source_url": "https://fbdes.bf/deuxieme-phase-du-guichet-teelba/",
        "source_raw": (
            "Le FBDES publie les formulaires de demande de financement subvention et credit pour le Guichet "
            "TEELBA 2025. Le depliant indique des montants de credit de 1 000 000 a 10 000 000 FCFA."
        ),
        "presentation": (
            "Le Guichet TEELBA du FBDES vise la relance economique et la reinsertion socio-economique des "
            "personnes et structures impactees par la crise securitaire au Burkina Faso."
        ),
        "eligibility": (
            "La source cible notamment les associations, groupements, societes cooperatives, TPE et PME. "
            "Les conditions precises varient selon la fenetre regionale et le type de financement demande."
        ),
        "funding": (
            "Le guichet combine subvention et credit. Les documents FBDES mentionnent des credits de "
            "1 000 000 a 10 000 000 FCFA ; le montant de subvention doit etre confirme dans le formulaire officiel."
        ),
        "calendar": (
            "Les formulaires 2025 sont disponibles. La prochaine fenetre de depot active doit etre confirmee "
            "sur le site FBDES avant toute preparation de dossier."
        ),
        "procedure": (
            "Telecharger le formulaire subvention ou credit sur le site FBDES, verifier la zone geographique "
            "ouverte, puis constituer le dossier administratif et financier demande."
        ),
        "checks": (
            "Confirmer que la region du porteur est actuellement couverte, que la fenetre est ouverte et que "
            "le formulaire utilise correspond bien au type de financement recherche."
        ),
        "decision": (
            "Opportunite prioritaire a surveiller pour les TPE, PME, cooperatives et associations burkinabe "
            "ayant un projet de relance economique ou d'activite generatrice de revenus."
        ),
    },
    {
        "source_name": "CLE Burkina Faso - entrepreneuriat jeunes",
        "title": "CLE Burkina Faso - accompagnement entrepreneurial des jeunes",
        "organism": "Cultivons l'Esprit d'Entreprise",
        "organism_type": "programme national",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "incubation_et_formation",
        "sectors": ["entrepreneuriat", "formation", "incubation", "jeunesse", "innovation"],
        "beneficiaries": ["jeune", "entrepreneur", "porteur projet", "startup"],
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme national à suivre pour les cohortes, formations et appels à candidatures.",
        "source_url": "https://www.cle-bf.com/",
        "source_raw": (
            "CLE Burkina Faso est une source prioritaire de veille pour les programmes d'entrepreneuriat, "
            "formation et accompagnement des jeunes entrepreneurs."
        ),
        "presentation": (
            "CLE Burkina Faso accompagne des jeunes porteurs de projets dans la structuration, la formation "
            "et le developpement de leurs initiatives entrepreneuriales."
        ),
        "eligibility": (
            "Le programme cible principalement les jeunes entrepreneurs et porteurs de projets au Burkina Faso. "
            "Les criteres exacts dependent de chaque cohorte ou appel publie."
        ),
        "funding": (
            "L'appui peut inclure formation, accompagnement, mentorat et mise en relation. Tout financement "
            "direct doit etre confirme dans l'appel actif."
        ),
        "calendar": "Les ouvertures se font par cohortes ou appels. Verifier la fenetre active sur la source officielle.",
        "procedure": (
            "Consulter le site CLE, verifier l'appel ou programme en cours, puis suivre les consignes de "
            "candidature publiees."
        ),
        "checks": (
            "Confirmer la cohorte ouverte, l'age ou profil cible, la localisation, les documents attendus "
            "et la presence ou non d'un financement direct."
        ),
        "decision": (
            "Bonne piste pour un jeune porteur de projet au Burkina qui cherche d'abord a structurer son "
            "projet, acceder a un reseau et se preparer a de futurs financements."
        ),
    },
    {
        "source_name": "ABCA Burkina Faso - Faso Films Fonds",
        "title": "Faso Films Fonds - soutien aux projets cinéma et audiovisuel au Burkina Faso",
        "organism": "Agence Burkinabe de la Cinematographie et de l'Audiovisuel",
        "organism_type": "agence publique",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "aide_culturelle",
        "sectors": ["culture", "cinéma", "audiovisuel", "industries créatives", "export"],
        "beneficiaries": ["entreprise culturelle", "association", "producteur", "réalisateur", "créateur"],
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "La plateforme de soumission indique que le délai actuel est expiré ; garder en veille pour les prochaines sessions.",
        "source_url": "https://abca.bf/fonds/",
        "source_raw": (
            "Faso Films Fonds est un mecanisme public dedie au financement, au developpement et a la "
            "structuration de l'industrie cinematographique et audiovisuelle au Burkina Faso."
        ),
        "presentation": (
            "Faso Films Fonds soutient les projets cinematographiques et audiovisuels burkinabe a travers "
            "plusieurs composantes : developpement, production, postproduction, export et equipement."
        ),
        "eligibility": (
            "Les beneficiaires peuvent etre des societes, associations, auteurs, realisateurs ou structures "
            "burkinabe du cinema et de l'audiovisuel, selon la categorie de l'appel."
        ),
        "funding": (
            "Le fonds peut financer partiellement des depenses de developpement, production, postproduction, "
            "export ou equipement. Les plafonds exacts dependent du reglement et de la session ouverte."
        ),
        "calendar": (
            "La derniere fenetre de soumission affichee est fermee. La fiche reste utile pour surveiller la "
            "prochaine session officielle."
        ),
        "procedure": (
            "Lire le reglement Faso Films Fonds, verifier si la plateforme de soumission est ouverte, puis "
            "preparer les pieces artistiques, administratives et financieres."
        ),
        "checks": (
            "Confirmer l'ouverture effective de la session, la categorie du projet, le plafond de financement "
            "et les documents attendus avant toute candidature."
        ),
        "decision": (
            "Source importante pour les acteurs culturels burkinabe, mais a traiter comme opportunite de veille "
            "tant que la prochaine session n'est pas ouverte."
        ),
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        sources = {}
        for source_data in SOURCES:
            sources[source_data["name"]] = await upsert_source(db, source_data)

        # Les autres sources ont ete creees par add_burkina_actionable_sources.
        burkina_sources_by_name = {source["name"]: source for source in BURKINA_SOURCES}
        for source_name in {
            "FBDES Burkina Faso - Guichet Teelba",
            "CLE Burkina Faso - entrepreneuriat jeunes",
            "ABCA Burkina Faso - Faso Films Fonds",
        }:
            sources[source_name] = await upsert_source(db, burkina_sources_by_name[source_name])

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
