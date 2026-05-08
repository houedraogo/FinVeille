"""
Ajoute la source Orange Corners / OCIF dans la base si elle n'existe pas deja.
Usage : docker exec finveille-backend python -m app.data.add_orange_corners_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


ORANGE_CORNERS_SOURCE = {
    "name": "Orange Corners - OCIF",
    "organism": "Orange Corners",
    "country": "Afrique",
    "source_type": "organisation_internationale",
    "category": "public",
    "level": 1,
    "reliability": 4,
    "url": "https://www.orangecorners.com/more-than-incubation/orange-corners-innovation-fund-ocif/",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "single_program_page",
        "list_selector": "main article",
        "item_title_selector": "h1.article-title",
        "item_link_selector": "a[href='__none__']",
        "item_description_selector": ".article-content, .entry-content, .wp-block-post-content, main article",
        "detail_fetch": False,
        "detail_content_selector": "main article, .entry-content, .article-content",
        "allow_english_text": True,
        "assume_recurring_without_close_date": True,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Page officielle Orange Corners Innovation Fund (OCIF). "
        "Le contenu HTML public expose correctement le titre, les deux tracks de financement "
        "et les montants, ce qui permet une collecte single-program propre."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == ORANGE_CORNERS_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in ORANGE_CORNERS_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            return

        source = Source(**ORANGE_CORNERS_SOURCE)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
