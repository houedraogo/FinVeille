"""
Fix — Supprimer les fiches dupliquées (même titre + même pays, status=open).

Stratégie :
  - Même source : garder le meilleur completeness_score, rejeter l'autre
  - Sources différentes : garder la source la plus spécialisée (Bpifrance > aides-entreprises),
    rejeter le doublon de moindre qualité
  - Si le meilleur exemplaire est admin_only : le passer en auto_published avant de rejeter le doublon

Usage: docker exec kafundo-backend python -m app.data.fix_deduplicate_open_devices
"""
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # Identifier tous les groupes en doublon
        rows = await db.execute(text("""
            SELECT d.id, d.title, d.country, d.source_id, s.name as source_name,
                   d.created_at, d.completeness_score, d.validation_status
            FROM devices d
            JOIN sources s ON d.source_id = s.id
            WHERE (d.title, d.country) IN (
                SELECT title, country FROM devices
                WHERE status = 'open' AND validation_status != 'rejected'
                GROUP BY title, country HAVING COUNT(*) > 1
            )
            AND d.status = 'open'
            AND d.validation_status != 'rejected'
            ORDER BY d.title, d.completeness_score DESC, d.created_at ASC
        """))
        records = rows.fetchall()

        # Grouper par (title, country)
        groups: dict[tuple, list] = {}
        for r in records:
            key = (r.title, r.country)
            groups.setdefault(key, []).append(r)

        rejected = published = 0

        for (title, country), items in groups.items():
            if len(items) < 2:
                continue

            # Trier : meilleur score d'abord, puis le plus ancien
            items_sorted = sorted(items, key=lambda r: (-r.completeness_score, r.created_at))
            best = items_sorted[0]
            duplicates = items_sorted[1:]

            # Publier le meilleur s'il est encore admin_only
            if best.validation_status == 'admin_only':
                await db.execute(text("""
                    UPDATE devices SET validation_status='auto_published', updated_at=NOW()
                    WHERE id = :id
                """), {"id": best.id})
                published += 1

            # Rejeter les doublons
            for dup in duplicates:
                await db.execute(text("""
                    UPDATE devices SET validation_status='rejected', updated_at=NOW()
                    WHERE id = :id
                """), {"id": dup.id})
                rejected += 1

        await db.commit()
        print(f"Doublons rejetés : {rejected}")
        print(f"Meilleures versions publiées : {published}")

        # Vérification
        r = await db.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT title, country FROM devices
                WHERE status='open' AND validation_status != 'rejected'
                GROUP BY title, country HAVING COUNT(*) > 1
            ) t
        """))
        print(f"Groupes doublons restants : {r.scalar()}")


if __name__ == "__main__":
    asyncio.run(main())
