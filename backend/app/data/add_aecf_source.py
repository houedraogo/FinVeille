"""
Ajoute la source AECF dans la base si elle n'existe pas deja.
Usage : docker exec finveille-backend python -m app.data.add_aecf_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


AECF_SOURCE = {
    "name": "AECF - competitions et challenge funds",
    "organism": "Africa Enterprise Challenge Fund",
    "country": "Afrique",
    "source_type": "institution_regionale",
    "category": "public",
    "level": 1,
    "reliability": 4,
    "url": "https://www.aecfafrica.org/index.php/",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "editorial_funding",
        "list_selector": "ul.hero-slides > li",
        "item_title_selector": "h2, .page-title, h1.page-title",
        "item_link_selector": "a.text-button-hero",
        "item_description_selector": ".content .post, .text-label, .page-title, p",
        "detail_fetch": True,
        "detail_content_selector": "main, article, .content, .body-copy",
        "allow_english_text": True,
        "assume_standby_without_close_date": True,
        "detail_max_chars": 9000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Page d'accueil officielle AECF utilisee comme listing des competitions ouvertes. "
        "Configuration HTML ciblee sur les blocs hero 'Open competition' pour remonter "
        "plusieurs opportunites actives au lieu d'une seule competition."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == AECF_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in AECF_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            return

        source = Source(**AECF_SOURCE)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
