"""Ajoute des fiches Burkina Faso tres concretes issues de sources officielles."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from app.database import AsyncSessionLocal
from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.data.add_burkina_actionable_sources import SOURCES as BURKINA_SOURCES


SOURCE_NAMES = {
    "Service Public Burkina Faso - FASI secteur informel",
    "Service Public Burkina Faso - FAIJ entrepreneuriat jeunes",
    "Service Public Burkina Faso - FAPE cofinancement projets",
    "Service Public Burkina Faso - jeunes diplomes microprojets",
    "FDCT Burkina Faso - appels culture et tourisme",
}


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "Service Public Burkina Faso - FASI secteur informel",
        "title": "FASI Burkina Faso - pret pour micro-projets du secteur informel",
        "organism": "Fonds d'Appui au Secteur Informel",
        "organism_type": "fonds public",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "microcredit",
        "sectors": ["commerce", "artisanat", "agriculture", "services", "emploi"],
        "beneficiaries": ["microentrepreneur", "secteur informel", "groupement", "entrepreneur"],
        "amount_max": Decimal("1500000"),
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Procedure administrative permanente ; la disponibilite effective des credits doit etre confirmee aupres du FASI.",
        "source_url": "https://servicepublic.gov.bf/fiches/emploi-demande-de-financement-de-micro-projets-du-secteur-informel",
        "source_raw": "Le service public burkinabe presente la demande de financement de micro-projets du secteur informel. Le FASI octroie des prets aux porteurs de micro-projets.",
        "presentation": "Le FASI finance des micro-projets du secteur informel au Burkina Faso afin de creer ou consolider des emplois. La fiche est concrete pour un petit commerce, un atelier, une activite de services ou un groupement qui a deja une idee rentable.",
        "eligibility": "La source cible les acteurs du secteur informel de nationalite burkinabe, ages de 18 a 60 ans. Le projet doit etre rentable, createur d'emplois, capable de rembourser le credit, avec aval, garantie et apport personnel.",
        "funding": "L'appui prend la forme d'un pret. Le demandeur doit indiquer le montant sollicite, le motif de l'emprunt, la duree souhaitee, un aval, une garantie et un apport personnel d'au moins 10% du montant sollicite.",
        "calendar": "Guichet administratif recurrent, sans date limite unique publiee sur la fiche officielle.",
        "procedure": "Preparer une demande adressee au FASI avec l'identite du promoteur, son adresse complete, le montant demande, le motif de l'emprunt, la duree souhaitee, l'aval et la garantie proposee.",
        "checks": "Confirmer le plafond applicable, le lieu de depot, les pieces reellement demandees par l'antenne FASI, le taux, l'echeancier et les garanties acceptees.",
        "decision": "Bonne piste pour un microentrepreneur burkinabe du secteur informel qui peut documenter une activite rentable et accepter une logique de pret rembourse.",
    },
    {
        "source_name": "Service Public Burkina Faso - FAIJ entrepreneuriat jeunes",
        "title": "FAIJ Burkina Faso - formation entrepreneuriat et financement jeunes",
        "organism": "Fonds d'Appui aux Initiatives des Jeunes",
        "organism_type": "fonds public",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "formation_et_financement",
        "sectors": ["entrepreneuriat", "formation", "emploi", "jeunesse", "microentreprise"],
        "beneficiaries": ["jeune", "porteur projet", "entrepreneur", "femme", "personne handicapee"],
        "amount_min": Decimal("100000"),
        "amount_max": Decimal("5000000"),
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Procedure recurrente : les sessions de formation, enveloppes et guichets disponibles doivent etre confirmes localement.",
        "source_url": "https://servicepublic.gov.bf/fiches/formation-professionnelle-formation-en-entreprenariat",
        "source_raw": "La procedure Formation en entrepreneuriat mentionne les financements FAIJ de 200 000 a 2 000 000 FCFA pour les projets individuels, 5 000 000 FCFA pour les collectifs, et les subventions PPEJ de 100 000 a 5 000 000 FCFA.",
        "presentation": "Le parcours FAIJ/PPEJ combine sensibilisation a l'esprit d'entreprise, formation, encadrement au montage du plan d'affaires et financement des meilleurs projets.",
        "eligibility": "Pour le PFE, la source vise notamment les jeunes de 15 a 35 ans ayant une attestation de formation en entrepreneuriat et un projet generateur de revenus. Pour le PPEJ, le candidat doit etre burkinabe, age de 16 a 35 ans, scolarise ou alphabetise.",
        "funding": "Les financements FAIJ indiques vont de 200 000 a 2 000 000 FCFA pour les projets individuels et jusqu'a 5 000 000 FCFA pour les projets collectifs. Les financements PPEJ sont presentes comme des subventions de 100 000 a 5 000 000 FCFA.",
        "calendar": "Les sessions et enveloppes fonctionnent par programme. Verifier la fenetre active aupres du FAIJ ou du service competent.",
        "procedure": "S'inscrire ou se renseigner sur la formation en entrepreneuriat, preparer le plan d'affaires, obtenir l'aval ou parrain demande, puis suivre la procedure FAIJ/PPEJ.",
        "checks": "Confirmer la session ouverte, le cout de formation, les taux applicables, le differe de remboursement, le mentor/parrain requis et les pieces a fournir.",
        "decision": "Tres utile pour un jeune porteur de projet au Burkina qui a besoin a la fois de formation, de cadrage business et d'un premier financement modere.",
    },
    {
        "source_name": "Service Public Burkina Faso - FAPE cofinancement projets",
        "title": "FAPE Burkina Faso - cofinancement de projets productifs",
        "organism": "Fonds d'Appui a la Promotion de l'Emploi",
        "organism_type": "fonds public",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "cofinancement",
        "sectors": ["agriculture", "elevage", "artisanat", "transformation", "commerce", "btp", "transport"],
        "beneficiaries": ["entrepreneur", "pme", "artisan", "agriculteur", "porteur projet"],
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Procedure publique recurrente ; le canevas, les plafonds et les enveloppes disponibles doivent etre confirmes aupres du FAPE.",
        "source_url": "https://servicepublic.gov.bf/fiches/emploi-cofinancement-des-projets-agriculture-elevage-artisanat-et-transformation-des-produits-locaux-commerce-prestation-de-service-transport-et-btp",
        "source_raw": "La procedure officielle presente le cofinancement de projets en agriculture, elevage, artisanat, transformation de produits locaux, commerce, prestation de service, transport et BTP.",
        "presentation": "Le FAPE cofinance des projets productifs portes par des Burkinabe vivant au Burkina Faso. La fiche couvre des secteurs tres operationnels : agriculture, elevage, artisanat, transformation, commerce, services, transport et BTP.",
        "eligibility": "Le demandeur doit etre Burkinabe vivant au Burkina Faso, age de 18 a 64 ans, jouir de ses facultes et presenter un projet conforme au canevas du FAPE.",
        "funding": "La source officielle decrit un cofinancement de projet. Les montants, taux, garanties et apports personnels ne sont pas precises dans la fiche publique et doivent etre confirmes au guichet FAPE.",
        "calendar": "Guichet recurrent sans echeance unique affichee dans la fiche administrative.",
        "procedure": "Recuperer le canevas FAPE, formaliser le projet, chiffrer les besoins, puis deposer le dossier selon les consignes de l'antenne competente.",
        "checks": "Verifier le canevas actuel, les secteurs acceptes, le plafond mobilisable, l'apport demande, les garanties et le delai de traitement.",
        "decision": "Piste concrete pour un porteur de projet productif au Burkina qui cherche un cofinancement public et peut presenter un dossier chiffre.",
    },
    {
        "source_name": "Service Public Burkina Faso - jeunes diplomes microprojets",
        "title": "Burkina Faso - financement de microprojets pour jeunes diplomes",
        "organism": "Direction Generale de l'Insertion Professionnelle et de l'Emploi",
        "organism_type": "administration publique",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "microprojet_innovant",
        "sectors": ["innovation", "emploi", "jeunesse", "entrepreneuriat", "formation professionnelle"],
        "beneficiaries": ["jeune diplome", "jeune qualifie", "porteur projet", "startup"],
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Procedure administrative a verifier aupres de la Direction Generale de l'Insertion Professionnelle et de l'Emploi.",
        "source_url": "https://www.servicepublic.gov.bf/fiches/emploi-financement-des-microprojets-des-jeunes-diplomes-du-superieur",
        "source_raw": "La procedure officielle finance des projets innovants, structurants et porteurs d'emplois pour jeunes diplomes du superieur ou jeunes qualifies de centres de formation professionnelle.",
        "presentation": "Ce dispositif cible les microprojets innovants et porteurs d'emplois proposes par de jeunes diplomes ou jeunes qualifies au Burkina Faso.",
        "eligibility": "La source indique qu'il faut etre jeune, diplome des universites, instituts ou ecoles superieures, ou etre jeune qualifie issu d'un centre de formation professionnelle, et avoir un projet innovant.",
        "funding": "La fiche confirme une logique de financement de microprojets, mais ne publie pas le plafond dans l'extrait administratif. Le canevas PISJ est indique comme disponible a la Direction Generale de l'Insertion Professionnelle et de l'Emploi.",
        "calendar": "Aucun calendrier unique n'est publie ; contacter l'administration competente pour la fenetre ou le depot en cours.",
        "procedure": "Recuperer le canevas PISJ, preparer une note de projet innovant avec budget et emplois attendus, puis confirmer les modalites de depot aupres de la DGIE.",
        "checks": "Confirmer l'age limite, le diplome ou certificat accepte, le canevas PISJ, le montant possible, les criteres d'innovation et le lieu de depot.",
        "decision": "Bonne piste pour un jeune diplome qui veut transformer une idee innovante en microentreprise avec un dossier structure.",
    },
    {
        "source_name": "FDCT Burkina Faso - appels culture et tourisme",
        "title": "FDCT Burkina Faso - appels culture et tourisme a surveiller",
        "organism": "Fonds de Developpement Culturel et Touristique",
        "organism_type": "fonds public",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "subvention_et_credit_culture",
        "sectors": ["culture", "tourisme", "industries creatives", "patrimoine", "audiovisuel"],
        "beneficiaries": ["entreprise culturelle", "association", "cooperative", "collectivite", "createur"],
        "amount_min": Decimal("0"),
        "amount_max": Decimal("600000000"),
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "L'appel 2025 est une reference de veille ; verifier les prochains appels avant de le traiter comme candidature ouverte.",
        "source_url": "https://www.fdct-bf.org/Appel-a-projets-2025-du-FDCT-Une-opportunite-pour-les-promoteurs-culturels-et",
        "source_raw": "Le FDCT indique que l'appel a projets 2025 comprenait un volet credit de 600 millions FCFA et un volet subvention d'environ 427 millions FCFA, destine aux promoteurs culturels et touristiques.",
        "presentation": "Le FDCT est le guichet public burkinabe a surveiller pour les projets culturels, touristiques et d'industries creatives. L'appel 2025 a combine credit et subvention pour soutenir des initiatives a fort impact.",
        "eligibility": "La source mentionne notamment les entreprises, associations legalement constituees et porteurs de projets innovants a fort impact social et economique dans la culture ou le tourisme.",
        "funding": "Pour l'appel 2025, le FDCT a annonce un volet credit de 600 millions FCFA et un volet subvention d'environ 427 millions FCFA. Les montants par projet dependent des lignes directrices de chaque appel.",
        "calendar": "L'appel 2025 a ete lance le 1er aout 2025. Cette fiche doit servir de veille pour les prochains appels et communiques FDCT.",
        "procedure": "Surveiller la rubrique Appels a projets du FDCT, telecharger les lignes directrices et canevas, puis preparer le dossier artistique, economique et administratif.",
        "checks": "Confirmer qu'une fenetre est actuellement ouverte, choisir le bon volet credit ou subvention, verifier les lignes directrices et le calendrier officiel.",
        "decision": "Source prioritaire pour les promoteurs culturels et touristiques burkinabe, surtout si le projet combine creation, ancrage territorial, emploi et impact social.",
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        sources_by_name = {source["name"]: source for source in BURKINA_SOURCES}
        sources = {
            name: await upsert_source(db, sources_by_name[name])
            for name in SOURCE_NAMES
        }

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
