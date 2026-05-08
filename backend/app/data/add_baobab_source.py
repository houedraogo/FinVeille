"""
Ajoute la source Baobab Network dans la base si elle n'existe pas deja.
Usage : docker exec finveille-backend python -m app.data.add_baobab_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


BAOBAB_SOURCE = {
    "name": "Baobab Network - accelerator applications",
    "organism": "Baobab Network",
    "country": "Afrique",
    "source_type": "fonds_prive",
    "category": "private",
    "level": 1,
    "reliability": 4,
    "url": "https://thebaobabnetwork.com/apply-now/",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "single_program_page",
        "list_selector": "html",
        "item_title_selector": "h2, title",
        "item_link_selector": "a[href='__none__']",
        "item_description_selector": "main",
        "detail_fetch": False,
        "detail_content_selector": "main, .site-main, .faq-featured, .text-media",
        "allow_english_text": True,
        "assume_recurring_without_close_date": True,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Page officielle de candidature Baobab Network. "
        "Le HTML public expose le positionnement accelerator, le ticket de 100k USD, "
        "les criteres de base et la logique de candidatures en rolling basis."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == BAOBAB_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in BAOBAB_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            return

        source = Source(**BAOBAB_SOURCE)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
