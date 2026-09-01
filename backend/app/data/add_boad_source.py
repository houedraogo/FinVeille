"""
Ajoute la source BOAD (Banque Ouest Africaine de Developpement) via API WordPress.
Usage : docker exec kafundo-backend python -m app.data.add_boad_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source

# API WordPress backend de BOAD : admin.boad.org/wp-json/wp/v2/tender
# project_status=56 -> "Avis d'appel d'offre"  (83 items)
# project_status=50 -> "Avis de manifestation d'interet" (92 items)
# L'API retourne directement un tableau JSON (pas de wrapper).
BOAD_SOURCE = {
    "name": "BOAD - Appels d'offres et AMI",
    "organism": "Banque Ouest Africaine de Developpement (BOAD)",
    "country": "Afrique de l'Ouest",
    "source_type": "organisation_internationale",
    "category": "public",
    "level": 1,
    "reliability": 5,
    "url": "https://admin.boad.org/wp-json/wp/v2/tender?project_status=56%2C50&orderby=date&order=desc",
    "collection_mode": "api",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "items_path": "",
        "title_field": "title.rendered",
        "url_field": "link",
        "description_field": "excerpt.rendered",
        "raw_content_fields": ["title.rendered", "excerpt.rendered"],
        "assume_standby_without_close_date": True,
        "allow_english_text": False,
        "pagination": {
            "type": "page",
            "page_param": "page",
            "size_param": "per_page",
            "size_value": 25,
        },
    },
    "notes": (
        "API WordPress backend BOAD (admin.boad.org). "
        "Filtre project_status=56 (Avis AO, 83 items) + 50 (AMI, 92 items). "
        "La page publique boad.org est en JS-only (Inertia.js), "
        "mais l'API WP REST est accessible sans authentification. "
        "Les liens pointent vers admin.boad.org (redirect vers boad.org en prod). "
        "IDs statuts : 56=Avis AO, 50=AMI, 58=Passation marche, 1228=Plan passation."
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
        else:
            source = Source(**BOAD_SOURCE)
            db.add(source)
            await db.commit()
            await db.refresh(source)
            print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
