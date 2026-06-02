from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


NOW = datetime.now(timezone.utc)


GENERIC_VC4A_TITLES = [
    "Startup Battlefield",
    "VP AI Foundry",
    "iHatch – Cohort 5",
    "iHatch - Cohort 5",
    "develoPPP Ventures Kenya, Rwanda, Tanzania",
    "Offre Cloudvisor pour startups accompagnées par VC4A",
]

EXPIRED_OR_WEAK_TITLES = [
    "FNEC Bénin - appels environnement et climat",
]


SOURCES: list[dict[str, Any]] = [
    {
        "name": "SAFINE Burkina Faso - financement MPME",
        "organism": "SAFINE SA",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "institution_financiere",
        "level": 1,
        "url": "https://www.safine.bf/",
        "collection_mode": "manual",
        "check_frequency": "monthly",
        "reliability": 4,
        "category": "private",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "burkina_mpme"},
        "notes": "Source officielle SAFINE: microfinance, crédit d'exploitation, crédit d'équipement et accompagnement des micro, petites et moyennes entreprises au Burkina Faso.",
    },
    {
        "name": "La Fabrique Burkina Faso - impact et incubation",
        "organism": "La Fabrique",
        "country": "Burkina Faso",
        "region": "Afrique de l'Ouest",
        "source_type": "incubateur",
        "level": 1,
        "url": "https://www.lafabrique-bf.com/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "afrique_ouest"},
        "notes": "Source officielle: incubation, accélération, formation, financement et accompagnement d'entreprises sociales au Burkina Faso.",
    },
    {
        "name": "ADPME e-PME Benin - opportunites PME",
        "organism": "Agence de Développement des PME du Bénin",
        "country": "Bénin",
        "region": "Afrique de l'Ouest",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://epme.adpme.bj/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "qualified_manual", "market": "benin_pme"},
        "notes": "Plateforme officielle e-PME Bénin pour opportunités de financement, formation, marché et accompagnement des MPME.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "SAFINE Burkina Faso - financement MPME",
        "title": "SAFINE Burkina Faso - crédits et accompagnement des MPME",
        "organism": "SAFINE SA",
        "organism_type": "institution financière",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "microfinance",
        "sectors": ["entrepreneuriat", "pme", "commerce", "artisanat", "formalisation"],
        "beneficiaries": ["entrepreneur", "pme", "tpe", "mpme", "micro entreprise", "entreprise informelle"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.safine.bf/",
        "source_raw": "SAFINE SA se positionne comme institution nationale de microfinance pour favoriser l'accès des micro, petites et moyennes entreprises aux financements et faciliter leur croissance et leur formalisation progressive au Burkina Faso.",
        "presentation": "SAFINE est une institution burkinabè de microfinance dédiée aux micro, petites et moyennes entreprises. Elle propose des crédits d'exploitation, des crédits d'équipement, des engagements par signature et des services d'accompagnement.",
        "eligibility": "Cette piste concerne surtout les MPME, entrepreneurs, commerçants, artisans et entreprises en formalisation au Burkina Faso. Les conditions exactes dépendent du produit financier demandé et de la capacité de remboursement.",
        "funding": "L'appui peut prendre la forme de crédit d'exploitation, de crédit d'équipement commercial, de cautions liées aux marchés et de services non financiers comme le suivi, le conseil, l'accompagnement et la formation.",
        "calendar": "Dispositif permanent: la demande se fait selon les produits ouverts par SAFINE et la disponibilité des agences ou points de service.",
        "procedure": "Consulter les produits sur le site officiel, contacter SAFINE ou se rendre en agence pour vérifier le produit adapté, les garanties éventuelles et les pièces à fournir.",
        "checks": "Confirmer les taux, frais, garanties, durées de remboursement et pièces demandées avant toute demande de crédit.",
        "decision": "Bonne piste pour une petite entreprise burkinabè qui cherche un financement de trésorerie, d'équipement ou un accompagnement vers la formalisation.",
    },
    {
        "source_name": "La Fabrique Burkina Faso - impact et incubation",
        "title": "La Fabrique Burkina Faso - incubation et financement d'entreprises sociales",
        "organism": "La Fabrique",
        "organism_type": "incubateur",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "incubation",
        "sectors": ["entrepreneuriat", "impact", "agriculture", "social", "formation"],
        "beneficiaries": ["entrepreneur", "porteur projet", "startup", "pme", "entreprise sociale", "ong"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.lafabrique-bf.com/",
        "source_raw": "La Fabrique accélère, structure et renforce les projets à impact. Le site présente l'incubation, l'accélération, la formation et le financement pour entrepreneurs sociaux et organisations engagées au Burkina Faso.",
        "presentation": "La Fabrique est un accélérateur d'impact basé au Burkina Faso. Elle accompagne les entrepreneurs sociaux, entreprises engagées et organisations qui veulent structurer leur modèle, renforcer leur équipe, accéder à des formations et mobiliser des financements.",
        "eligibility": "Cette piste concerne surtout les entrepreneurs sociaux, startups, PME, organisations à impact et porteurs de projets basés au Burkina Faso ou en Afrique de l'Ouest. Le projet doit avoir une dimension sociale, environnementale ou territoriale claire.",
        "funding": "L'appui principal est l'incubation, l'accélération, la formation, le conseil et la mise en relation. La Fabrique indique aussi des outils financiers pour aider au développement des entreprises sociales; les tickets exacts dépendent des programmes ouverts.",
        "calendar": "Dispositif à suivre en continu. Les programmes et opportunités sont publiés selon les cohortes, actualités ou appels du moment.",
        "procedure": "Consulter la page officielle, vérifier les opportunités en cours, puis contacter La Fabrique ou candidater via le formulaire indiqué pour le programme concerné.",
        "checks": "Confirmer le programme ouvert, les critères sectoriels, la forme exacte de l'appui et l'existence d'un financement direct avant de candidater.",
        "decision": "À prioriser pour les projets à impact au Burkina Faso qui cherchent plus qu'une subvention: structuration, réseau et accompagnement.",
    },
    {
        "source_name": "ADPME e-PME Benin - opportunites PME",
        "title": "ADPME e-PME Bénin - opportunités de financement et accompagnement PME",
        "organism": "Agence de Développement des PME du Bénin",
        "organism_type": "agence nationale",
        "country": "Bénin",
        "region": "Bénin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "appui_pme",
        "sectors": ["entrepreneuriat", "pme", "finance", "formation", "marché"],
        "beneficiaries": ["pme", "mpme", "entreprise", "entrepreneur", "startup"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://epme.adpme.bj/",
        "source_raw": "e-PME Bénin est la plateforme numérique de l'ADPME pour aider les MPME à accéder aux opportunités de financement, de formation et de marché.",
        "presentation": "La plateforme e-PME Bénin centralise les opportunités de l'ADPME pour les micro, petites et moyennes entreprises: accompagnement, formation, opportunités de financement, accès au marché et programmes de croissance.",
        "eligibility": "La cible principale concerne les MPME, startups et entreprises béninoises formalisées ou en structuration. Les critères varient selon chaque programme ou cohorte publiée sur la plateforme.",
        "funding": "Selon le programme, l'appui peut porter sur l'accompagnement stratégique, la structuration financière, la préparation à l'accès au crédit ou la mise en relation avec des partenaires.",
        "calendar": "Source récurrente: les appels et cohortes sont publiés au fil de l'eau. Les dates doivent être vérifiées sur chaque opportunité e-PME.",
        "procedure": "Créer un compte ou consulter les opportunités sur e-PME Bénin, sélectionner le programme pertinent, puis déposer les informations demandées par l'ADPME.",
        "checks": "Vérifier si une cohorte est ouverte, les pièces requises, les conditions par secteur et les délais de sélection.",
        "decision": "Bonne porte d'entrée nationale pour une PME béninoise qui veut identifier des programmes officiels d'accompagnement et de financement.",
    },
]


async def _mark_admin_only(db, titles: list[str], reason: str, *, expired: bool = False) -> int:
    result = await db.execute(select(Device).where(Device.title.in_(titles)))
    devices = result.scalars().all()
    for device in devices:
        device.validation_status = "admin_only"
        device.user_quality_decision = "admin_only"
        device.user_quality_reasons = list(
            dict.fromkeys([*(device.user_quality_reasons or []), reason])
        )
        if expired:
            device.status = "expired"
        device.updated_at = NOW
        device.last_verified_at = NOW
    return len(devices)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        masked_vc4a = await _mark_admin_only(db, GENERIC_VC4A_TITLES, "vc4a_generique_hors_priorite_lancement")
        masked_expired = await _mark_admin_only(db, EXPIRED_OR_WEAK_TITLES, "date_cloture_passee_ou_source_a_reverifier", expired=True)

        sources = {}
        for source_data in SOURCES:
            sources[source_data["name"]] = await upsert_source(db, source_data)

        counts = {"created": 0, "updated": 0}
        for device_data in DEVICES:
            status = await upsert_device(db, device_data, sources[device_data["source_name"]])
            counts[status] += 1

        await db.commit()
        print({"masked_vc4a": masked_vc4a, "masked_expired": masked_expired, "sources": len(sources), **counts})


if __name__ == "__main__":
    asyncio.run(main())
