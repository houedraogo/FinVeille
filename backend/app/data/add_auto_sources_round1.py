"""Ajoute une premiere vague de sources automatiques de veille.

Usage:
    docker exec kafundo-backend python -m app.data.add_auto_sources_round1
"""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


EDITORIAL_RSS_CONFIG = {
    "source_kind": "editorial_opportunities",
    "allow_english_text": True,
    "assume_standby_without_close_date": True,
}

SOURCES = [
    {
        "name": "Cascade Funding Hub - open calls",
        "organism": "Cascade Funding Hub",
        "country": "Union europeenne",
        "source_type": "portail_specialise",
        "category": "public",
        "level": 1,
        "reliability": 4,
        "url": "https://cascadefunding.eu/feed/",
        "collection_mode": "rss",
        "check_frequency": "daily",
        "is_active": True,
        "config": {
            **EDITORIAL_RSS_CONFIG,
            "source_kind": "editorial_funding",
            "priority_topics": ["cascade funding", "open call", "sme", "startup", "innovation"],
        },
        "notes": (
            "Flux RSS specialise cascade funding / open calls. Source utile pour PME, startups et consortiums "
            "innovation. Les fiches restent en admin_only si le titre/date/type ne sont pas suffisamment qualifies."
        ),
    },
    {
        "name": "Opportunities For Africans - appels a candidatures",
        "organism": "Opportunities For Africans",
        "country": "Afrique",
        "source_type": "portail_specialise",
        "category": "public",
        "level": 2,
        "reliability": 3,
        "url": "https://www.opportunitiesforafricans.com/category/call-for-applications/feed/",
        "collection_mode": "rss",
        "check_frequency": "daily",
        "is_active": True,
        "config": EDITORIAL_RSS_CONFIG,
        "notes": (
            "Flux large d'appels africains. Publier seulement apres qualification automatique stricte ou revue admin."
        ),
    },
    {
        "name": "Opportunity Desk - grants",
        "organism": "Opportunity Desk",
        "country": "International",
        "source_type": "portail_specialise",
        "category": "public",
        "level": 2,
        "reliability": 3,
        "url": "https://opportunitydesk.org/category/grants/feed/",
        "collection_mode": "rss",
        "check_frequency": "daily",
        "is_active": True,
        "config": EDITORIAL_RSS_CONFIG,
        "notes": "Flux de grants international. Source volontairement sous garde-fou admin_only par defaut.",
    },
    {
        "name": "fundsforNGOs - latest calls",
        "organism": "fundsforNGOs",
        "country": "International",
        "source_type": "portail_specialise",
        "category": "public",
        "level": 2,
        "reliability": 3,
        "url": "https://www2.fundsforngos.org/category/latest-funds-for-ngos/feed/",
        "collection_mode": "rss",
        "check_frequency": "daily",
        "is_active": True,
        "config": EDITORIAL_RSS_CONFIG,
        "notes": "Flux appels/propositions ONG. Source large, a qualifier avant publication publique.",
    },
]


async def run() -> dict:
    results: list[dict] = []
    async with AsyncSessionLocal() as db:
        for payload in SOURCES:
            source = (
                await db.execute(select(Source).where(Source.name == payload["name"]))
            ).scalar_one_or_none()
            action = "updated"
            if source:
                for key, value in payload.items():
                    setattr(source, key, value)
            else:
                source = Source(**payload)
                db.add(source)
                action = "created"
            await db.flush()
            results.append(
                {
                    "action": action,
                    "name": source.name,
                    "mode": source.collection_mode,
                    "url": source.url,
                    "active": source.is_active,
                }
            )
        await db.commit()
    return {"sources": len(results), "items": results}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
