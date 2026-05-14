from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


async def run(names: list[str]) -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Source).where(Source.name.in_(names)))).scalars().all()
        return [
            {
                "id": str(source.id),
                "name": source.name,
                "url": source.url,
                "active": source.is_active,
                "mode": source.collection_mode,
                "config": source.config,
            }
            for source in rows
        ]


def main() -> None:
    names = sys.argv[1:]
    if not names:
        raise SystemExit("Usage: python -m app.data.inspect_source_config <source name> [...]")
    print(json.dumps(asyncio.run(run(names)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
