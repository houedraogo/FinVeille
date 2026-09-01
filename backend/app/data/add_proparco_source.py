"""
Ajoute la source Proparco (filiale AFD, financement secteur prive Afrique).
Usage : docker exec kafundo-backend python -m app.data.add_proparco_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


PROPARCO_SOURCE = {
    "name": "Proparco - Appels a propositions",
    "organism": "Proparco / AFD",
    "country": "Afrique",
    "source_type": "institution_publique",
    "category": "public",
    "level": 1,
    "reliability": 5,
    "url": "https://www.proparco.fr/fr/appels-a-propositions",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "listing",
        "list_selector": ".views-row, article, .node--type-appel, .appel-propositions, .card",
        "item_title_selector": "h3, h2, .node__title, a",
        "item_link_selector": "a",
        "item_description_selector": ".field--body, .summary, .field--name-body, p",
        "detail_fetch": True,
        "detail_content_selector": ".field--name-body, .node__content, article, main",
        "allow_english_text": False,
        "assume_standby_without_close_date": True,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 3},
    },
    "notes": (
        "Proparco : filiale de l'AFD dediee au financement du secteur prive en Afrique et dans les pays en developpement. "
        "Finance PME, infrastructures, energie, agriculture. "
        "Site Drupal gouvernemental francais, generalement accessible."
    ),
}

PROPARCO_IMPACT_SOURCE = {
    "name": "AFD - Appels a propositions Afrique",
    "organism": "Agence Francaise de Developpement",
    "country": "Afrique",
    "source_type": "institution_publique",
    "category": "public",
    "level": 2,
    "reliability": 5,
    "url": "https://www.afd.fr/fr/appels-a-propositions",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "listing",
        "list_selector": ".views-row, article, .node, .card, .appel-item",
        "item_title_selector": "h3, h2, .node__title, a",
        "item_link_selector": "a",
        "item_description_selector": ".field--body, .summary, p",
        "detail_fetch": True,
        "detail_content_selector": ".field--name-body, .node__content, article, main",
        "allow_english_text": False,
        "assume_standby_without_close_date": True,
        "detail_max_chars": 12000,
        "pagination": {"max_pages": 5},
    },
    "notes": (
        "Agence Francaise de Developpement : appels a propositions multi-pays dont beaucoup ciblent l'Afrique. "
        "Financement ONG, entreprises, collectivites. Site Drupal gouvernemental."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        for source_data in [PROPARCO_SOURCE, PROPARCO_IMPACT_SOURCE]:
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
