"""
Ajoute la source AfDB (African Development Bank) dans la base.
Usage : docker exec kafundo-backend python -m app.data.add_afdb_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


AFDB_SOURCE = {
    "name": "African Development Bank - Appels a propositions",
    "organism": "African Development Bank (AfDB)",
    "country": "Afrique",
    "source_type": "institution_regionale",
    "category": "public",
    "level": 1,
    "reliability": 5,
    "url": "https://www.afdb.org/fr/appels-a-propositions-et-offres",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "listing",
        "list_selector": ".views-row, article, .node, tr, .procurement-item",
        "item_title_selector": "h3, h2, td.title, a",
        "item_link_selector": "a",
        "item_description_selector": ".summary, p, td",
        "detail_fetch": True,
        "detail_content_selector": ".field--name-body, article main, .node__content, main",
        "allow_english_text": True,
        "assume_standby_without_close_date": False,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 5},
    },
    "notes": (
        "Banque Africaine de Developpement (BAD/AfDB) - Abidjan. "
        "Finance des projets souverains et prives sur tout le continent africain. "
        "Appels a propositions pour ONG, entreprises, consultants. "
        "Bilinguisme EN/FR : allow_english_text=True."
    ),
}

AFDB_FUND_SOURCE = {
    "name": "African Development Fund - Grants",
    "organism": "African Development Bank (AfDB)",
    "country": "Afrique",
    "source_type": "institution_regionale",
    "category": "public",
    "level": 2,
    "reliability": 5,
    "url": "https://www.afdb.org/en/topics-and-sectors/initiatives-partnerships/african-development-fund",
    "collection_mode": "html",
    "check_frequency": "monthly",
    "is_active": True,
    "config": {
        "source_kind": "single_program_page",
        "list_selector": "main, article, .field--name-body",
        "item_title_selector": "h1, h2",
        "item_link_selector": "a[href='__none__']",
        "item_description_selector": ".field--name-body, main, article",
        "detail_fetch": False,
        "allow_english_text": True,
        "assume_recurring_without_close_date": True,
        "detail_max_chars": 10000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Fonds Africain de Developpement (FAD) : guichet concessionnaire de l'AfDB pour les pays les moins avances. "
        "Subventions et prets a taux reduits. Page institutionnelle."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        for source_data in [AFDB_SOURCE, AFDB_FUND_SOURCE]:
            existing = await db.execute(
                select(Source).where(Source.name == source_data["name"])
            )
            source = existing.scalar_one_or_none()

            if source:
                for key, value in source_data.items():
                    setattr(source, key, value)
                await db.commit()
                await db.refresh(source)
                print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            else:
                source = Source(**source_data)
                db.add(source)
                await db.commit()
                await db.refresh(source)
                print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
