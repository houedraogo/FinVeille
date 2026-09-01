"""
Ajoute la source BOAD (Banque Ouest Africaine de Developpement) dans la base.
Usage : docker exec kafundo-backend python -m app.data.add_boad_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


BOAD_SOURCE = {
    "name": "BOAD - Appels a propositions",
    "organism": "Banque Ouest Africaine de Developpement",
    "country": "Afrique de l'Ouest",
    "source_type": "institution_regionale",
    "category": "public",
    "level": 2,
    "reliability": 5,
    "url": "https://www.boad.org/appels-a-propositions/",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "listing",
        "list_selector": ".appel-item, article, .post, .entry, .card, li.appel",
        "item_title_selector": "h2, h3, .entry-title, a",
        "item_link_selector": "a",
        "item_description_selector": ".excerpt, .summary, p",
        "detail_fetch": True,
        "detail_content_selector": ".entry-content, main article, .page-content, .contenu",
        "allow_english_text": False,
        "assume_standby_without_close_date": True,
        "detail_max_chars": 10000,
        "pagination": {"max_pages": 3},
    },
    "notes": (
        "Banque Ouest Africaine de Developpement (BOAD) - institution financiere de l'UEMOA. "
        "Finance des projets de developpement en Afrique de l'Ouest. "
        "Siege : Lome (Togo). URL a verifier lors du premier run : si la page /appels-a-propositions "
        "n'existe pas, essayer /actualites ou /appels-offres."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == BOAD_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in BOAD_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            return

        source = Source(**BOAD_SOURCE)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
