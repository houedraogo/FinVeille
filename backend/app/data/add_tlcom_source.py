"""
Ajoute la source TLcom Capital dans la base si elle n'existe pas deja.

Usage : docker exec finveille-backend python -m app.data.add_tlcom_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


TLCOM_SOURCE = {
    "name": "TLcom Capital - pitch us",
    "organism": "TLcom Capital",
    "country": "Afrique",
    "source_type": "fonds_prive",
    "category": "private",
    "level": 1,
    "reliability": 4,
    "url": "https://tlcomcapital.com/contact-us",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "single_program_page",
        "list_selector": "html",
        "item_title_selector": "title, h3, h1",
        "item_link_selector": "a[href='__none__']",
        "item_description_selector": "main, .Main-content, .site-wrapper, body",
        "detail_fetch": False,
        "detail_content_selector": "main, .Main-content, .site-wrapper, body",
        "allow_english_text": True,
        "assume_recurring_without_close_date": True,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Page officielle TLcom Capital de prise de contact pour les fondateurs. "
        "Le HTML public expose le point d'entree 'Pitch Us' et la these d'investissement "
        "sur des startups africaines technologiques et scalables."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == TLCOM_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in TLCOM_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            return

        source = Source(**TLCOM_SOURCE)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
