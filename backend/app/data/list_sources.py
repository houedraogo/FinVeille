import asyncio
import json

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


async def run() -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Source.name, Source.organism, Source.url, Source.category, Source.collection_mode)
                .order_by(Source.name.asc())
            )
        ).all()
        return [
            {
                "name": name,
                "organism": organism,
                "url": url,
                "category": category,
                "collection_mode": collection_mode,
            }
            for name, organism, url, category, collection_mode in rows
        ]


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
