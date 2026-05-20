"""Audit compact des opportunites Afrique visibles cote utilisateur."""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.services.device_service import DeviceService


PUBLIC_TYPES = [
    "subvention",
    "pret",
    "avance_remboursable",
    "garantie",
    "credit_impot",
    "exoneration",
    "aap",
    "appel_a_projets",
    "ami",
    "accompagnement",
    "concours",
]

COUNTRY_ALIASES = {
    "Burkina Faso": ["Burkina Faso"],
    "Benin": ["Bénin", "Benin"],
    "Cote d'Ivoire": ["Côte d'Ivoire", "Cote d'Ivoire"],
    "Afrique / regional": ["Afrique", "Afrique de l'Ouest", "International"],
}


async def main() -> None:
    async with AsyncSessionLocal() as db:
        print("Opportunites visibles et actionnables")
        for label, countries in COUNTRY_ALIASES.items():
            expanded_countries = countries
            if label != "Afrique / regional":
                expanded_countries = DeviceService._expanded_country_filter(countries)
            query = (
                select(func.count())
                .select_from(Device)
                .where(
                    Device.validation_status.in_(["auto_published", "approved", "validated"]),
                    Device.user_quality_decision.in_(["publish", "publish_with_caution"]),
                    Device.status.in_(["open", "recurring"]),
                    Device.device_type.in_(PUBLIC_TYPES),
                    Device.country.in_(expanded_countries),
                )
            )
            count = (await db.execute(query)).scalar() or 0
            print(f"- {label}: {count} (avec opportunites regionales)")

        recent_query = (
            select(Device.country, Device.title, Device.status, Device.device_type, Device.source_url)
            .where(
                Device.ai_rewrite_model == "curation_afrique_round3",
                Device.validation_status.in_(["auto_published", "approved", "validated"]),
            )
            .order_by(Device.country, Device.title)
        )
        print("\nFiches curation_afrique_round3")
        for country, title, status, device_type, source_url in (await db.execute(recent_query)).all():
            print(f"- {country} | {status} | {device_type} | {title} | {source_url}")


if __name__ == "__main__":
    asyncio.run(main())
