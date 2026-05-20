from __future__ import annotations

import asyncio
import json

from app.database import AsyncSessionLocal
from app.services.visible_quality_service import build_visible_quality_audit


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        return await build_visible_quality_audit(db, limit=40)


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
