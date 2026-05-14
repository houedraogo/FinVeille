from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source
from app.tasks.collect_tasks import _collect_source_async


async def run(source_name: str) -> None:
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(select(Source).where(Source.name == source_name))
        ).scalar_one_or_none()
        if not source:
            print(f"[NOT_FOUND] {source_name}")
            return
        source_id = str(source.id)

    await _collect_source_async(source_id)
    print(f"[OK] collecte terminee pour {source_name} ({source_id})")


def main() -> None:
    source_name = " ".join(sys.argv[1:]).strip()
    if not source_name:
        raise SystemExit('Usage: python -m app.data.collect_source_by_name "Nom de source"')
    asyncio.run(run(source_name))


if __name__ == "__main__":
    main()
