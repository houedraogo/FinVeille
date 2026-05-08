"""
Debug rapide d'une source : connecteur brut puis normalisation.

Usage:
    docker exec finveille-backend python -m app.data.debug_source_collection "Nom de source"
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.collector.api_connector import APIConnector
from app.collector.html_connector import HTMLConnector
from app.collector.normalizer import Normalizer
from app.database import AsyncSessionLocal
from app.models.source import Source


async def run(source_name: str) -> None:
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(select(Source).where(Source.name == source_name))
        ).scalar_one_or_none()
        if not source:
            print(f"[NOT_FOUND] {source_name}")
            return

        source_dict = {
            "id": str(source.id),
            "name": source.name,
            "organism": source.organism,
            "country": source.country,
            "url": source.url,
            "collection_mode": source.collection_mode,
            "config": source.config or {},
        }

        if source.collection_mode == "api":
            connector = APIConnector(source_dict)
        else:
            connector = HTMLConnector(source_dict)

        result = await connector.collect()
        print(f"success={result.success}")
        print(f"error={result.error}")
        print(f"raw_items={len(result.items)}")

        for item in result.items[:5]:
            print("--- RAW ITEM ---")
            print(f"title={item.title}")
            print(f"url={item.url}")
            print(f"raw_content={((item.raw_content or '')[:300]).replace(chr(10), ' ')}")

            normalized = Normalizer(source_dict).normalize(item)
            print("--- NORMALIZED ---")
            print("normalized=None" if normalized is None else f"title={normalized.get('title')} status={normalized.get('status')} validation={normalized.get('validation_status')}")


if __name__ == "__main__":
    source_name = " ".join(sys.argv[1:]).strip()
    if not source_name:
        print('Usage: python -m app.data.debug_source_collection "Nom de source"')
        raise SystemExit(1)
    asyncio.run(run(source_name))
