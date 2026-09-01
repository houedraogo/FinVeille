"""
Ajoute les sources USAID pour l'Afrique dans la base.
Usage : docker exec kafundo-backend python -m app.data.add_usaid_africa_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


USAID_WEST_AFRICA_SOURCE = {
    "name": "USAID - Appels Afrique de l'Ouest",
    "organism": "USAID (United States Agency for International Development)",
    "country": "Afrique de l'Ouest",
    "source_type": "organisation_internationale",
    "category": "public",
    "level": 1,
    "reliability": 5,
    "url": "https://www.usaid.gov/west-africa-regional/work-with-us",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "listing",
        "list_selector": "article, .views-row, .node, .card, li",
        "item_title_selector": "h2, h3, a",
        "item_link_selector": "a",
        "item_description_selector": ".summary, p, .field--name-body",
        "detail_fetch": True,
        "detail_content_selector": ".field--name-body, main article, .node__content",
        "allow_english_text": True,
        "assume_standby_without_close_date": True,
        "detail_max_chars": 10000,
        "pagination": {"max_pages": 3},
    },
    "notes": (
        "USAID Bureau Afrique de l'Ouest : opportunites de financement pour ONG, "
        "entreprises, institutions locales. "
        "Subventions (grants), contrats, partenariats public-prive. "
        "Site .gov americain, accessible sans protection."
    ),
}

USAID_AFRICA_SOURCE = {
    "name": "USAID - Appels Afrique subsaharienne",
    "organism": "USAID (United States Agency for International Development)",
    "country": "Afrique",
    "source_type": "organisation_internationale",
    "category": "public",
    "level": 2,
    "reliability": 5,
    "url": "https://www.usaid.gov/sub-saharan-africa/work-with-us",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "listing",
        "list_selector": "article, .views-row, .node, .card, li",
        "item_title_selector": "h2, h3, a",
        "item_link_selector": "a",
        "item_description_selector": ".summary, p, .field--name-body",
        "detail_fetch": True,
        "detail_content_selector": ".field--name-body, main article, .node__content",
        "allow_english_text": True,
        "assume_standby_without_close_date": True,
        "detail_max_chars": 10000,
        "pagination": {"max_pages": 3},
    },
    "notes": (
        "USAID Bureau Afrique subsaharienne : financement programmes regionaux. "
        "Agriculture, sante, gouvernance, education. Contenu en anglais."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        for source_data in [USAID_WEST_AFRICA_SOURCE, USAID_AFRICA_SOURCE]:
            existing = await db.execute(
                select(Source).where(Source.name == source_data["name"])
            )
            source = existing.scalar_one_or_none()

            if source:
                for key, value in source_data.items():
                    setattr(source, key, value)
                await db.commit()
                await db.refresh(source)
                print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            else:
                source = Source(**source_data)
                db.add(source)
                await db.commit()
                await db.refresh(source)
                print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
