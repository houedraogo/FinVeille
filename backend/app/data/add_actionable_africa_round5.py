"""Ajoute des opportunites regionales et nationales tres proches de la candidature."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

from app.database import AsyncSessionLocal
from app.data.add_actionable_africa_round3 import upsert_device, upsert_source


SOURCES: list[dict[str, Any]] = [
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
        "notes": "Source officielle Seme City pour RISE 2, programme d'acceleration des PME et startups beninoises.",
    },
    {
        "name": "Fonds Pierre Castel - Prix Pierre Castel 2026",
        "organism": "Fonds Pierre Castel",
        "country": "Afrique",
        "region": "Bénin, Burkina Faso, Côte d'Ivoire",
        "source_type": "concours",
        "level": 1,
        "url": "https://www.fonds-pierre-castel.org/prix-pierre-castel/prix-pierre-castel-2026/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "agro_afrique"},
        "notes": "Source officielle du Prix Pierre Castel 2026 pour entrepreneurs des systemes alimentaires africains.",
    },
    {
        "name": "AfCFTA Startup Acceleration 2026",
        "organism": "AfCFTA Secretariat / Korea Africa Foundation",
        "country": "Afrique",
        "region": "Afrique",
        "source_type": "accelerateur",
        "level": 1,
        "url": "https://vc4a.com/afcfta-visions/afcfta-startup-acceleration-partnership-program-2026/?lang=fr",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 4,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "africa_startups"},
        "notes": "Page de candidature VC4A pour le programme AfCFTA Startup Acceleration & Partnership 2026.",
    },
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "Seme City - RISE 2 Benin",
        "title": "RISE 2 Benin - acceleration et financement des PME et startups",
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
        "source_raw": "RISE 2 s'adresse aux jeunes entreprises en phase d'amorcage et aux PME innovantes au Benin. Candidature avant le 7 juin 2026. Appui financier jusqu'a 7,5 millions ou 28 millions FCFA selon categorie.",
        "presentation": "RISE 2 est un programme d'acceleration porte par le Gouvernement du Benin, Seme City et l'ADPME pour aider les entreprises beninoises a fort potentiel a structurer leur croissance.",
        "eligibility": "Le programme cible deux profils: jeunes entreprises en phase d'amorcage avec chiffre d'affaires entre 0 et 30 millions FCFA, et PME innovantes avec chiffre d'affaires entre 15 et 50 millions FCFA.",
        "funding": "L'appui peut atteindre 7,5 millions FCFA pour certaines jeunes entreprises et 28 millions FCFA pour les PME innovantes, avec assistance technique, formation, coaching et mise en reseau.",
        "calendar": "Les candidatures sont ouvertes jusqu'au 7 juin 2026.",
        "procedure": "Consulter la page officielle RISE, verifier la categorie de candidature, preparer les informations financieres et deposer le dossier via www.rise2.bj.",
        "checks": "Verifier la categorie exacte, le chiffre d'affaires admissible, les pieces demandees et les conditions de cofinancement avant depot.",
        "decision": "Tres bonne opportunite pour une PME ou startup beninoise qui veut accelerer sa croissance avec financement et accompagnement.",
    },
    {
        "source_name": "Fonds Pierre Castel - Prix Pierre Castel 2026",
        "title": "Prix Pierre Castel 2026 - entrepreneurs des systemes alimentaires",
        "organism": "Fonds Pierre Castel",
        "organism_type": "fondation",
        "country": "Afrique",
        "region": "Bénin, Burkina Faso, Côte d'Ivoire",
        "zone": "Afrique",
        "geographic_scope": "international",
        "device_type": "concours",
        "aid_nature": "prix_entrepreneurial",
        "sectors": ["agriculture", "agroalimentaire", "economie circulaire", "logistique", "innovation alimentaire"],
        "beneficiaries": ["entrepreneur", "startup", "pme", "entreprise"],
        "amount_min": Decimal("25000"),
        "amount_max": Decimal("35000"),
        "currency": "EUR",
        "open_date": date(2026, 4, 1),
        "close_date": date(2026, 5, 30),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://www.fonds-pierre-castel.org/prix-pierre-castel/prix-pierre-castel-2026/",
        "source_raw": "Le Prix Pierre Castel 2026 est ouvert du 1er avril au 30 mai 2026 dans sept pays dont Benin, Burkina Faso et Cote d'Ivoire. Il soutient les entrepreneurs des systemes alimentaires avec dotation, mentorat et accompagnement.",
        "presentation": "Le Prix Pierre Castel soutient des entrepreneurs africains qui transforment durablement les systemes alimentaires. L'edition 2026 concerne notamment le Benin, le Burkina Faso et la Cote d'Ivoire.",
        "eligibility": "Les candidats doivent avoir entre 18 et 45 ans, etre ressortissants et residents d'un pays eligible, etre fondateurs ou cofondateurs d'une entreprise legalement constituee et active depuis au moins deux ans.",
        "funding": "Le prix combine une dotation financiere, du mentorat, du coaching personnalise, de la mise en reseau et une visibilite panafricaine. Le gain national est d'environ 25 000 EUR, avec un complement possible pour le laureat panafricain.",
        "calendar": "Candidatures ouvertes du 1er avril au 30 mai 2026. Finale panafricaine prevue le 30 septembre 2026 a Cotonou.",
        "procedure": "Deposer la candidature sur la plateforme officielle du Prix Pierre Castel avec les documents de l'entreprise et le projet de developpement.",
        "checks": "Verifier la plateforme de candidature, les pieces obligatoires, les criteres pays et la date limite du 30 mai 2026.",
        "decision": "A prioriser pour les entrepreneurs agroalimentaires deja formalises au Benin, Burkina Faso ou Cote d'Ivoire.",
    },
    {
        "source_name": "AfCFTA Startup Acceleration 2026",
        "title": "AfCFTA Startup Acceleration 2026 - startups africaines a fort potentiel",
        "organism": "AfCFTA Secretariat / Korea Africa Foundation",
        "organism_type": "programme international",
        "country": "Afrique",
        "region": "Afrique",
        "zone": "Afrique",
        "geographic_scope": "international",
        "device_type": "accompagnement",
        "aid_nature": "acceleration_internationale",
        "sectors": ["fintech", "e-commerce", "logistique", "agritech", "industrie", "plateformes digitales"],
        "beneficiaries": ["startup", "entrepreneur", "pme", "entreprise"],
        "open_date": date(2026, 5, 12),
        "close_date": date(2026, 5, 24),
        "status": "open",
        "is_recurring": False,
        "source_url": "https://vc4a.com/afcfta-visions/afcfta-startup-acceleration-partnership-program-2026/?lang=fr",
        "source_raw": "AfCFTA Startup Acceleration & Partnership Program 2026 supports African startups with international expansion, market access, partnerships and investor exposure. Application deadline: 24 May 2026.",
        "presentation": "Ce programme d'acceleration vise a aider des startups africaines a fort potentiel a se renforcer, acceder a de nouveaux marches et nouer des partenariats avec l'ecosysteme coreen et international.",
        "eligibility": "Les startups doivent avoir un modele innovant et scalable, demontrer une traction sur leur marche et viser une expansion internationale dans des secteurs alignes avec les priorites AfCFTA.",
        "funding": "Le programme apporte surtout mentorat, capacite business, acces marche, mise en relation investisseurs et partenariats internationaux. La source ne communique pas de subvention directe garantie.",
        "calendar": "Date limite de candidature: 24 mai 2026.",
        "procedure": "Deposer le formulaire de candidature et les documents demandes via la page VC4A/AfCFTA.",
        "checks": "Verifier l'eligibilite sectorielle, les documents requis, la maturite du projet et la capacite d'expansion internationale avant de candidater.",
        "decision": "Opportunite urgente pour une startup africaine deja active qui cherche une ouverture internationale et des partenaires.",
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
