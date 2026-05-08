"""
Ajoute la source AECF dediee au programme DIFEC si elle n'existe pas deja.

Usage : docker exec finveille-backend python -m app.data.add_aecf_difec_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


AECF_DIFEC_SOURCE = {
    "name": "AECF - DIFEC",
    "organism": "Africa Enterprise Challenge Fund",
    "country": "Afrique",
    "source_type": "institution_regionale",
    "category": "public",
    "level": 1,
    "reliability": 4,
    "url": "https://www.aecfafrica.org/approach/our-programmes/renewable-energy/react-2-0-regional-digital-innovation-fund-for-energy-climate-programme-difec/",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "single_program_page",
        "list_selector": "html",
        "item_title_selector": "title, h1, h2",
        "item_link_selector": "a[href='__none__']",
        "item_description_selector": "main, article, .content, body",
        "detail_fetch": False,
        "detail_content_selector": "main, article, .content, body",
        "allow_english_text": True,
        "assume_standby_without_close_date": True,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Source AECF dediee au programme DIFEC pour mieux couvrir l'appel digital energy & climate "
        "sans dependre du carrousel general du site."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == AECF_DIFEC_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in AECF_DIFEC_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            return

        source = Source(**AECF_DIFEC_SOURCE)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
