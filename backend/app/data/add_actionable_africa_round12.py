from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.data.add_actionable_africa_round3 import upsert_device, upsert_source
from app.database import AsyncSessionLocal


NOW = datetime.now(timezone.utc)


SOURCES: list[dict[str, Any]] = [
    {
        "name": "FNM Benin - financement PRODIJ",
        "organism": "Fonds National de la Microfinance",
        "country": "Bénin",
        "region": "Afrique de l'Ouest",
        "source_type": "fonds_public",
        "level": 1,
        "url": "https://www.fnm.bj/financement-prodij/",
        "collection_mode": "manual",
        "check_frequency": "weekly",
        "reliability": 5,
        "category": "public",
        "is_active": True,
        "config": {"source_kind": "single_program_page", "market": "benin_jeunes"},
        "notes": "Page officielle FNM publiée en mai 2026 sur le financement PRODIJ pour jeunes vulnérables au Bénin.",
    }
]


DEVICES: list[dict[str, Any]] = [
    {
        "source_name": "FNM Benin - financement PRODIJ",
        "title": "FNM Bénin - financement PRODIJ pour jeunes vulnérables",
        "organism": "Fonds National de la Microfinance",
        "organism_type": "fonds public",
        "country": "Bénin",
        "region": "Bénin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "microfinance_jeunes",
        "sectors": ["entrepreneuriat", "jeunesse", "formation", "microfinance", "emploi"],
        "beneficiaries": ["jeune entrepreneur", "entrepreneur", "femme entrepreneure", "porteur projet", "tpe"],
        "status": "recurring",
        "is_recurring": True,
        "source_url": "https://www.fnm.bj/financement-prodij/",
        "source_raw": "Le Fonds National de la Microfinance présente le financement PRODIJ. Les bénéficiaires visés sont les jeunes vulnérables des 77 communes du Bénin, âgés de 15 à 30 ans, peu ou pas instruits, en situation de chômage ou de sous-emploi, avec une attention particulière aux femmes et aux jeunes vivant dans des zones vulnérables.",
        "presentation": "Le financement PRODIJ porté par le Fonds National de la Microfinance vise à faciliter l'insertion économique de jeunes vulnérables au Bénin, notamment via la formation professionnelle, l'accompagnement et l'accès à des solutions de financement adaptées.",
        "eligibility": "La cible concerne les jeunes vulnérables des 77 communes du Bénin, âgés de 15 à 30 ans, peu ou pas instruits, en chômage ou sous-emploi. La source mentionne une attention particulière aux femmes et aux jeunes des zones vulnérables.",
        "funding": "L'appui peut combiner formation, accompagnement et financement via les mécanismes du FNM/PRODIJ. Les montants, conditions de crédit, garanties et modalités pratiques doivent être confirmés auprès du FNM ou des opérateurs de terrain.",
        "calendar": "Page publiée en mai 2026. Le dispositif doit être suivi comme programme actif/récurrent, avec confirmation des vagues de financement localement.",
        "procedure": "Consulter la page officielle du FNM, vérifier les canaux d'inscription PRODIJ dans la commune concernée, puis préparer les informations personnelles et le projet d'activité demandé.",
        "checks": "Confirmer la commune couverte, l'âge requis, les périodes de sélection, les conditions de financement, les pièces demandées et l'opérateur local responsable.",
        "decision": "Bonne opportunité pour les jeunes béninois qui cherchent un premier appui économique, surtout lorsque le besoin porte sur formation, insertion et microfinancement.",
    }
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
