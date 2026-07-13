"""
Fix 5 — Clôturer les fiches expirées encore affichées "open".

Contexte : 111 fiches avaient status='open' alors que leur close_date était dépassée.
Ces fiches apparaissaient dans le catalogue comme opportunités actives alors qu'elles
ne l'étaient plus, dégradant l'expérience utilisateur.

Cette correction est normalement effectuée par la tâche Celery daily_catalog_quality_control,
mais les fiches importées avant l'activation de cette tâche n'avaient pas été traitées.

Usage: docker exec kafundo-backend python -m app.data.fix_expire_open_past_close_date
"""
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            UPDATE devices
            SET status = 'expired', updated_at = NOW()
            WHERE status = 'open'
              AND close_date IS NOT NULL
              AND close_date < CURRENT_DATE
        """))
        count = result.rowcount
        await db.commit()
        print(f"Fiches passées à 'expired' : {count}")

        row = await db.execute(text("""
            SELECT COUNT(*) FROM devices
            WHERE status = 'open'
              AND close_date IS NOT NULL
              AND close_date < CURRENT_DATE
        """))
        print(f"Fiches expirées encore 'open' restantes : {row.scalar()}")


if __name__ == "__main__":
    asyncio.run(main())
