from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.database import AsyncSessionLocal


NOW = datetime.now(timezone.utc)


SOURCES: list[dict[str, Any]] = [
    {
        "name": "SGPME Cote d'Ivoire - garanties credit PME",
        "organism": "Société de Garantie des crédits aux PME ivoiriennes",
        "country": "Côte d'Ivoire",
        "region": "Afrique de l'Ouest",
        "source_type": "fonds_public",
        "level": 1,
        "url": "https://www.sgpme.ci/faq/",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "cote_ivoire_pme_garantie"},
        "notes": "FAQ officielle SGPME détaillant les garanties de crédit pour TPE, PME et ETI ivoiriennes.",
    },
    {
        "name": "BIIC BEI Benin - financement PME agricoles",
        "organism": "BIIC / Banque Européenne d'Investissement",
        "country": "Bénin",
        "region": "Afrique de l'Ouest",
        "source_type": "banque",
        "level": 2,
        "url": "https://www.biic-bank.com/fr/actualite/biic-et-bei-sassocient-pour-accompagner-les-pme-et-eti-agricoles-au-benin.html",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 5,
        "category": "private",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "benin_agri_pme_credit"},
        "notes": "Ligne BIIC/BEI 2026 pour le financement de PME et ETI agricoles au Bénin.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "SGPME Cote d'Ivoire - garanties credit PME",
        "title": "SGPME Côte d'Ivoire - garantie de crédit pour TPE, PME et ETI",
        "organism": "Société de Garantie des crédits aux PME ivoiriennes",
        "organism_type": "établissement financier public",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "garantie",
        "aid_nature": "garantie_credit_pme",
        "sectors": ["entrepreneuriat", "agriculture", "industrie", "services", "commerce", "finance"],
        "beneficiaries": ["tpe", "pme", "eti", "entrepreneur", "jeune entrepreneur", "femme entrepreneure"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.sgpme.ci/faq/",
        "source_raw": (
            "La SGPME garantit les crédits accordés aux PME ivoiriennes en partageant au moins 50% des risques avec les établissements financiers partenaires. "
            "La FAQ officielle précise que la garantie individuelle concerne les TPE, PME et ETI ivoiriennes, avec des critères de chiffre d'affaires, de localisation en Côte d'Ivoire et d'activité licite. "
            "Le niveau de couverture indiqué oscille entre 50% et 80% du montant du financement accordé."
        ),
        "presentation": (
            "La SGPME facilite l'accès au crédit bancaire des entreprises ivoiriennes en apportant une garantie aux banques et microfinances partenaires."
        ),
        "eligibility": (
            "La garantie cible les TPE, PME et ETI ayant leur siège et leur activité principale en Côte d'Ivoire, exerçant une activité licite, avec un capital détenu au moins à 50% par des Ivoiriens selon la FAQ officielle."
        ),
        "funding": (
            "La SGPME ne verse pas directement une subvention. Elle couvre une partie du risque bancaire, généralement entre 50% et 80% du financement accordé, avec une commission de garantie indiquée entre 1% et 1,5% du montant garanti."
        ),
        "calendar": (
            "Dispositif permanent. La demande se fait dans le cadre d'une demande de crédit auprès d'une banque ou institution financière partenaire."
        ),
        "procedure": (
            "L'entreprise introduit d'abord une demande de crédit auprès d'une banque partenaire. Après accord de principe, la banque initie la demande de garantie SGPME via la plateforme dédiée."
        ),
        "checks": (
            "Vérifier la banque partenaire, le type de crédit couvert, les pièces demandées, le niveau de garantie applicable et les éventuelles exclusions sectorielles avant de conseiller la démarche."
        ),
        "decision": (
            "Très bonne piste pour une PME ivoirienne qui cherche un prêt bancaire mais manque de garanties suffisantes pour sécuriser son dossier."
        ),
    },
    {
        "source_name": "BIIC BEI Benin - financement PME agricoles",
        "title": "BIIC / BEI Bénin - financement des PME agricoles",
        "organism": "BIIC / Banque Européenne d'Investissement",
        "organism_type": "banque",
        "country": "Bénin",
        "region": "Bénin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "credit_pme_agricole",
        "sectors": ["agriculture", "agroalimentaire", "transformation", "coton", "soja", "anacarde", "entrepreneuriat"],
        "beneficiaries": ["pme", "eti", "cooperative", "femme entrepreneure", "exploitant agricole", "entrepreneur"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.biic-bank.com/fr/actualite/biic-et-bei-sassocient-pour-accompagner-les-pme-et-eti-agricoles-au-benin.html",
        "source_raw": (
            "La BIIC et la Banque Européenne d'Investissement ont signé le 30 mars 2026 un contrat de financement visant à soutenir les chaînes de valeur agricoles au Bénin. "
            "La source officielle BIIC indique une enveloppe pouvant atteindre 100 millions d'euros pour financer des projets portés par des PME et ETI. "
            "Les objectifs incluent l'accès au financement, les chaînes de valeur agricoles, l'égalité de genre et l'autonomisation économique des femmes."
        ),
        "presentation": (
            "La ligne BIIC/BEI renforce l'accès au financement pour les PME et ETI actives dans les chaînes de valeur agricoles au Bénin."
        ),
        "eligibility": (
            "La cible concerne principalement les PME et ETI béninoises actives dans les chaînes de valeur agricoles. La source met notamment en avant les filières agricoles et l'inclusion économique des femmes."
        ),
        "funding": (
            "L'enveloppe globale annoncée peut atteindre 100 millions d'euros, mais le montant accessible à chaque entreprise dépendra de l'analyse bancaire de la BIIC et des conditions propres au projet."
        ),
        "calendar": (
            "Dispositif bancaire structurant signé en mars 2026. Les fenêtres, produits et conditions opérationnelles doivent être confirmés auprès de la BIIC."
        ),
        "procedure": (
            "Contacter la BIIC, présenter le besoin de financement agricole, vérifier l'éligibilité du projet, puis constituer un dossier bancaire avec les états financiers et éléments de projet demandés."
        ),
        "checks": (
            "Confirmer les filières éligibles, les montants par entreprise, les garanties demandées, les maturités de prêt, les taux et l'existence d'une assistance technique associée."
        ),
        "decision": (
            "Bonne opportunité pour une PME agricole béninoise déjà structurée, notamment dans les filières soja, coton, anacarde ou transformation agricole."
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
