"""
Vérifie que les migrations ont installé les colonnes de reformulation IA.

Usage:
    docker exec kafundo-backend python -m app.data.ensure_ai_rewrite_columns
"""
import asyncio
import json

from app.schema_readiness import assert_schema_ready


async def run() -> dict[str, object]:
    await assert_schema_ready()
    return {"ok": True, "schema": "alembic-head"}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
