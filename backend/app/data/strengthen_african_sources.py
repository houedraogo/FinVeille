from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


TEF_SOURCE = {
    "name": "Tony Elumelu Foundation - entrepreneurship programme",
    "organism": "Tony Elumelu Foundation",
    "country": "Afrique",
    "source_type": "fondation",
    "category": "private",
    "level": 1,
    "reliability": 4,
    "url": "https://www.tonyelumelufoundation.org/tef-entrepreneurship-programme/",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "single_program_page",
        "list_selector": "html",
        "item_title_selector": "title, h2",
        "item_link_selector": "a[href='__none__']",
        "item_description_selector": ".entry-content, .elementor, body",
        "detail_fetch": False,
        "detail_content_selector": ".entry-content, .elementor, body",
        "allow_english_text": True,
        "assume_recurring_without_close_date": True,
        "detail_max_chars": 14000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Source officielle TEF Entrepreneurship Programme. Configuree en page programme unique pour eviter "
        "la page d'accueil bruitée et produire une fiche recurrente exploitable."
    ),
}

PROPARCO_SOURCE_PATCH = {
    "name": "PROPARCO - projets secteur prive",
    "is_active": False,
    "collection_mode": "manual",
    "notes": (
        "Source qualifiee mais desactivee en collecte automatique: l'URL actuelle pointe vers une base de projets "
        "historiques finances par Proparco, pas vers des appels ou une page de candidature directement exploitable. "
        "A remplacer par une page produit/apply avant reactivation."
    ),
}


async def _upsert(db, payload: dict) -> str:
    source = (
        await db.execute(select(Source).where(Source.name == payload["name"]))
    ).scalar_one_or_none()
    if source:
        for key, value in payload.items():
            if key == "name":
                continue
            setattr(source, key, value)
        return "updated"

    source = Source(**payload)
    db.add(source)
    return "created"


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        tef_action = await _upsert(db, TEF_SOURCE)
        proparco_action = await _upsert(db, PROPARCO_SOURCE_PATCH)
        await db.commit()
        return {
            "tony_elumelu_foundation": tef_action,
            "proparco": proparco_action,
        }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
