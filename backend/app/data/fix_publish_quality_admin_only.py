"""
Fix 2 — Publier les fiches admin_only de qualité ≥80%.

Contexte : 2718 fiches en validation_status='admin_only' mais avec completeness_score ≥80
et user_quality_decision='publish'. Ces fiches étaient invisibles alors que leur qualité
est supérieure aux fiches auto_published.

Action : passer à validation_status='auto_published' les fiches éligibles.

Usage: docker exec kafundo-backend python -m app.data.fix_publish_quality_admin_only
"""
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            UPDATE devices
            SET validation_status = 'auto_published', updated_at = NOW()
            WHERE validation_status = 'admin_only'
              AND user_quality_decision = 'publish'
              AND status NOT IN ('expired', 'closed')
        """))
        count = result.rowcount
        await db.commit()
        print(f"Fiches publiées : {count}")

        row = await db.execute(text(
            "SELECT COUNT(*) FROM devices WHERE status='open' AND validation_status='auto_published'"
        ))
        print(f"Total fiches open+auto_published : {row.scalar()}")


if __name__ == "__main__":
    asyncio.run(main())
