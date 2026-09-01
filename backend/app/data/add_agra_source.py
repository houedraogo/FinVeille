"""
Ajoute la source AGRA (Alliance for a Green Revolution in Africa).
Usage : docker exec kafundo-backend python -m app.data.add_agra_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


AGRA_SOURCE = {
    "name": "AGRA - Grants & Funding Opportunities",
    "organism": "AGRA (Alliance for a Green Revolution in Africa)",
    "country": "Afrique",
    "source_type": "organisation_internationale",
    "category": "public",
    "level": 1,
    "reliability": 4,
    "url": "https://agra.org/grants-opportunities/",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "listing",
        "list_selector": "article, .grant-item, .opportunity, .card, .post",
        "item_title_selector": "h2, h3, .entry-title, a",
        "item_link_selector": "a",
        "item_description_selector": ".excerpt, .summary, p, .entry-summary",
        "detail_fetch": True,
        "detail_content_selector": ".entry-content, article, main, .post-content",
        "allow_english_text": True,
        "assume_standby_without_close_date": True,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 3},
    },
    "notes": (
        "AGRA (Alliance pour une revolution verte en Afrique) - subventions et financements "
        "pour l'agriculture durable en Afrique subsaharienne. "
        "Finance ONG, cooperatives agricoles, startups agritech. "
        "Site WordPress, contenu en anglais."
    ),
}

AGRA_CALLS_SOURCE = {
    "name": "AGRA - Calls for Proposals",
    "organism": "AGRA (Alliance for a Green Revolution in Africa)",
    "country": "Afrique",
    "source_type": "organisation_internationale",
    "category": "public",
    "level": 2,
    "reliability": 4,
    "url": "https://agra.org/calls-for-proposals/",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "listing",
        "list_selector": "article, .call-item, .card, .post",
        "item_title_selector": "h2, h3, .entry-title, a",
        "item_link_selector": "a",
        "item_description_selector": ".excerpt, .summary, p",
        "detail_fetch": True,
        "detail_content_selector": ".entry-content, article, main",
        "allow_english_text": True,
        "assume_standby_without_close_date": False,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 3},
    },
    "notes": (
        "Appels a propositions specifiques de l'AGRA. "
        "Programmes cibles sur les systemes alimentaires, semences, finance agricole."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        for source_data in [AGRA_SOURCE, AGRA_CALLS_SOURCE]:
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
