"""
Ajoute la source Janngo Capital dans la base si elle n'existe pas deja.

Usage : docker exec finveille-backend python -m app.data.add_janngo_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


JANGGO_SOURCE = {
    "name": "Janngo Capital - investment thesis",
    "organism": "Janngo Capital",
    "country": "Afrique",
    "source_type": "fonds_prive",
    "category": "private",
    "level": 1,
    "reliability": 4,
    "url": "https://www.janngo.com/investments/",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "single_program_page",
        "list_selector": "html",
        "item_title_selector": "title, h2",
        "item_link_selector": "a[href='__none__']",
        "item_description_selector": "main, .site",
        "detail_fetch": False,
        "detail_content_selector": "main, .site, .container, .card-body",
        "allow_english_text": True,
        "assume_recurring_without_close_date": True,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Page officielle Janngo Capital sur sa these d'investissement. "
        "Le HTML public expose le ticket d'investissement, le positionnement early stage, "
        "la couverture panafricaine et le point d'entree contact pour les fondateurs."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == JANGGO_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in JANGGO_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            return

        source = Source(**JANGGO_SOURCE)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
