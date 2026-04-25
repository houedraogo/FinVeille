"""
Ajoute les colonnes de reformulation IA sur les bases locales existantes.

Usage:
    docker exec kafundo-backend python -m app.data.ensure_ai_rewrite_columns
"""
import asyncio
import json

from sqlalchemy import text

from app.database import AsyncSessionLocal


async def run() -> dict[str, object]:
    async with AsyncSessionLocal() as db:
        statements = [
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS ai_rewritten_sections_json JSON NULL",
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS ai_rewrite_status VARCHAR(50) NOT NULL DEFAULT 'pending'",
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS ai_rewrite_model VARCHAR(120) NULL",
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS ai_rewrite_checked_at TIMESTAMPTZ NULL",
            "CREATE INDEX IF NOT EXISTS ix_devices_ai_rewrite_status ON devices (ai_rewrite_status)",
        ]
        for statement in statements:
            await db.execute(text(statement))
        await db.commit()
    return {"ok": True, "columns": 4, "indexes": 1}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
