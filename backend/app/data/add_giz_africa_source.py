"""
Ajoute les sources GIZ (Deutsche Gesellschaft fur Internationale Zusammenarbeit) pour l'Afrique.
Usage : docker exec kafundo-backend python -m app.data.add_giz_africa_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


GIZ_WEST_AFRICA_SOURCE = {
    "name": "GIZ - Appels a propositions Afrique de l'Ouest",
    "organism": "GIZ (Deutsche Gesellschaft fur Internationale Zusammenarbeit)",
    "country": "Afrique de l'Ouest",
    "source_type": "organisation_internationale",
    "category": "public",
    "level": 2,
    "reliability": 4,
    "url": "https://www.giz.de/en/worldwide/west_africa.html",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "listing",
        "list_selector": "article, .news-item, .project-item, .teaserbox, li",
        "item_title_selector": "h2, h3, .headline, a",
        "item_link_selector": "a",
        "item_description_selector": ".teaser__text, .summary, p",
        "detail_fetch": True,
        "detail_content_selector": ".richtext, article, main, .field-items",
        "allow_english_text": True,
        "assume_standby_without_close_date": True,
        "detail_max_chars": 10000,
        "pagination": {"max_pages": 3},
    },
    "notes": (
        "GIZ (cooperation technique allemande) - programmes en Afrique de l'Ouest. "
        "Appels a propositions pour ONG, entreprises locales, institutions. "
        "Contenu principalement en anglais. "
        "Le site GIZ peut etre protege, verifier lors du premier run."
    ),
}

GIZ_CALLS_SOURCE = {
    "name": "GIZ - Calls for proposals Africa",
    "organism": "GIZ (Deutsche Gesellschaft fur Internationale Zusammenarbeit)",
    "country": "Afrique",
    "source_type": "organisation_internationale",
    "category": "public",
    "level": 1,
    "reliability": 4,
    "url": "https://www.giz.de/en/html/calls_for_proposals.html",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "listing",
        "list_selector": "table tr, .row, article, li",
        "item_title_selector": "td a, h3, h2, a",
        "item_link_selector": "a",
        "item_description_selector": "td, p, .teaser__text",
        "detail_fetch": True,
        "detail_content_selector": ".richtext, article, main",
        "allow_english_text": True,
        "assume_standby_without_close_date": False,
        "detail_max_chars": 10000,
        "pagination": {"max_pages": 5},
    },
    "notes": (
        "Page officielle des appels a propositions de la GIZ (tous pays). "
        "Filtrer les resultats Afrique au niveau de l'enrichisseur par country. "
        "Contenu en anglais/allemand."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        for source_data in [GIZ_WEST_AFRICA_SOURCE, GIZ_CALLS_SOURCE]:
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
