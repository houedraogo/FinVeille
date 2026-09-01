"""
Ajoute la source Tony Elumelu Foundation dans la base si elle n'existe pas deja.
Usage : docker exec kafundo-backend python -m app.data.add_tony_elumelu_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


TONY_ELUMELU_SOURCE = {
    "name": "Tony Elumelu Foundation - TEF Programme",
    "organism": "Tony Elumelu Foundation",
    "country": "Afrique",
    "source_type": "organisation_internationale",
    "category": "private",
    "level": 1,
    "reliability": 5,
    "url": "https://www.tonyelumelufoundation.org/tef-entrepreneurship-programme/",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "single_program_page",
        "list_selector": "main, .page-content, article",
        "item_title_selector": "h1, h2.entry-title",
        "item_link_selector": "a[href='__none__']",
        "item_description_selector": ".entry-content, .page-content, main article, .wp-block-post-content",
        "detail_fetch": False,
        "detail_content_selector": "main, .entry-content, .page-content",
        "allow_english_text": True,
        "assume_recurring_without_close_date": True,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Programme phare de la Tony Elumelu Foundation : 5 000 USD de capital d'amorçage + "
        "formation + mentorat pour ~1 000 entrepreneurs africains/an. "
        "Candidatures ouvertes annuellement (janvier-mars). "
        "Site WordPress accessible publiquement."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == TONY_ELUMELU_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in TONY_ELUMELU_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            return

        source = Source(**TONY_ELUMELU_SOURCE)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
