"""
Ajoute la source AWDF dans la base si elle n'existe pas deja.

Usage : docker exec finveille-backend python -m app.data.add_awdf_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


AWDF_SOURCE = {
    "name": "AWDF - grants and resourcing",
    "organism": "African Women's Development Fund",
    "country": "Afrique",
    "source_type": "fondation",
    "category": "private",
    "level": 1,
    "reliability": 4,
    "url": "https://awdf.org/what-we-do/resourcing/",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "single_program_page",
        "list_selector": "html",
        "item_title_selector": "h2.t-head-page, title",
        "item_link_selector": "a[href='__none__']",
        "item_description_selector": "main",
        "detail_fetch": False,
        "detail_content_selector": "main, .container, .accordion, .impact",
        "allow_english_text": True,
        "assume_recurring_without_close_date": True,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Page officielle AWDF sur le grantmaking et le resourcing. "
        "Le HTML public expose les criteres de subvention, les exclusions et un point d'entree "
        "vers la demande de grant, sans date limite publique unique."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == AWDF_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in AWDF_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            return

        source = Source(**AWDF_SOURCE)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
