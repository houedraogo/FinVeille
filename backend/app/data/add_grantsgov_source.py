"""
Ajoute la source Grants.gov (opportunites US gouvernement pour l'Afrique).
Usage : docker exec kafundo-backend python -m app.data.add_grantsgov_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


GRANTSGOV_AFRICA_SOURCE = {
    "name": "Grants.gov - Financements US pour l'Afrique",
    "organism": "US Government (Grants.gov)",
    "country": "Afrique",
    "source_type": "organisation_internationale",
    "category": "public",
    "level": 2,
    "reliability": 5,
    "url": "https://apply07.grants.gov/grantsws/rest/opportunities/search/",
    "collection_mode": "api",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "use_post": True,
        "post_body": {
            "keyword": "sub-saharan africa",
            "oppStatuses": "posted",
        },
        "post_body_offset_field": "startRecordNum",
        "post_body_size_field": "rows",
        "pagination": {
            "type": "offset",
            "size_value": 25,
        },
        "items_path": "oppHits",
        "title_field": "title",
        "url_template": "https://www.grants.gov/search-grants?cfda={number}",
        "description_field": "agency",
        "raw_content_fields": ["title", "agency", "openDate", "closeDate", "cfdaList", "number"],
        "allow_english_text": True,
        "assume_standby_without_close_date": False,
    },
    "notes": (
        "API officielle Grants.gov — portail des subventions du gouvernement americain. "
        "Recherche par mot-cle 'africa' parmi les opportunites actives (posted). "
        "Agences typiques : DOS-AF (Bureau of African Affairs), DOL-ILAB, HHS-CDC, USDA-NIFA. "
        "Utilise un POST JSON avec pagination par startRecordNum. "
        "L'enrichisseur filtre automatiquement les resultats pertinents pour l'Afrique."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == GRANTSGOV_AFRICA_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in GRANTSGOV_AFRICA_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
        else:
            source = Source(**GRANTSGOV_AFRICA_SOURCE)
            db.add(source)
            await db.commit()
            await db.refresh(source)
            print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
