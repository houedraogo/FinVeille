"""
Ajoute ou met a jour la source VC4A Programs.

Usage:
docker exec finveille-backend python -m app.data.add_vc4a_source
"""
from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


VC4A_SOURCE = {
    "name": "VC4A - startup programs and opportunities",
    "organism": "VC4A",
    "country": "Afrique",
    "source_type": "ecosysteme_startup",
    "category": "private",
    "level": 1,
    "reliability": 4,
    "url": "https://vc4a.com/programs/?lang=en",
    "collection_mode": "html",
    "check_frequency": "daily",
    "is_active": True,
    "config": {
        "source_kind": "listing",
        "list_selector": "main li, article, .card, .program-card",
        "item_title_selector": "h4 a, h3 a, h2 a, h4, h3, h2",
        "item_link_selector": "h4 a[href], h3 a[href], h2 a[href], a[href*='/programs/']",
        "item_description_selector": "p, .description, .excerpt, .summary",
        "detail_fetch": False,
        "detail_content_selector": "main, article, .entry-content, .content, body",
        "detail_max_chars": 12000,
        "allow_english_text": True,
        "assume_standby_without_close_date": True,
        "pagination": {
            "max_pages": 2,
            "next_selector": "a.next, a[rel='next'], .pagination a.next",
        },
    },
    "notes": (
        "Source africaine prioritaire pour programmes startups, accelerateurs, competitions et opportunites "
        "de financement. La collecte cible les cartes programme VC4A et garde les fiches sans deadline en "
        "standby pour eviter de publier des opportunites ambiguës comme ouvertes."
    ),
}


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(select(Source).where(Source.name == VC4A_SOURCE["name"]))
        ).scalar_one_or_none()
        action = "updated"
        if source:
            for key, value in VC4A_SOURCE.items():
                setattr(source, key, value)
        else:
            source = Source(**VC4A_SOURCE)
            db.add(source)
            action = "created"

        await db.commit()
        await db.refresh(source)
        return {
            "action": action,
            "id": str(source.id),
            "name": source.name,
            "url": source.url,
            "active": source.is_active,
        }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
