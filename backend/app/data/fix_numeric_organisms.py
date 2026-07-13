"""
Fix 3 — Corriger les noms d'organismes corrompus (IDs numériques).

Contexte : le CSV aides-entreprises.fr stockait des IDs numériques internes dans la colonne
"financeurs" (ex: "123, 456"). Ces valeurs étaient copiées telles quelles dans le champ
organism. 2055 fiches affichaient un organisme comme "123" au lieu du vrai porteur.

Action : remplacer les organismes purement numériques par "DGE / aides-entreprises.fr"
pour les fiches de cette source. La colonne import_aides_entreprises_csv.py a aussi été
corrigée pour éviter la réapparition.

Usage: docker exec kafundo-backend python -m app.data.fix_numeric_organisms
"""
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal

SOURCE_ORGANISM = "DGE / aides-entreprises.fr"
SOURCE_NAME_PATTERN = "%aides aux entreprises (CSV)%"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(text(r"""
            UPDATE devices
            SET organism = :org, updated_at = NOW()
            WHERE organism ~ '^[\d\s,;/]+$'
              AND source_id = (
                  SELECT id FROM sources WHERE name LIKE :pattern LIMIT 1
              )
        """), {"org": SOURCE_ORGANISM, "pattern": SOURCE_NAME_PATTERN})
        count = result.rowcount
        await db.commit()
        print(f"Organismes corrigés : {count}")

        row = await db.execute(text(r"SELECT COUNT(*) FROM devices WHERE organism ~ '^\d+$'"))
        print(f"Organismes numériques restants : {row.scalar()}")


if __name__ == "__main__":
    asyncio.run(main())
