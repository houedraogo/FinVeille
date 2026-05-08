"""
Ajoute la source GSMA Innovation Fund dans la base si elle n'existe pas deja.
Usage : docker exec finveille-backend python -m app.data.add_gsma_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


GSMA_SOURCE = {
    "name": "GSMA Innovation Fund - calls",
    "organism": "GSMA",
    "country": "Afrique",
    "source_type": "organisation_internationale",
    "category": "private",
    "level": 1,
    "reliability": 3,
    "url": "https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/the-gsma-innovation-fund/",
    "collection_mode": "html",
    "check_frequency": "monthly",
    "is_active": False,
    "config": {
        "source_kind": "single_program_page",
        "detail_fetch": False,
        "detail_content_selector": "main, article, .entry-content, .post-content",
        "allow_english_text": True,
        "assume_standby_without_close_date": True,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Source officielle GSMA Innovation Fund pour suivre les appels tech/mobile/IA "
        "dans les LMICs avec forte composante Afrique. Le site est protege par Cloudflare : "
        "la collecte HTML classique peut retourner une page de challenge et doit donc rester "
        "en qualification manuelle tant qu'un contournement fiable n'est pas mis en place."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == GSMA_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in GSMA_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            return

        source = Source(**GSMA_SOURCE)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
