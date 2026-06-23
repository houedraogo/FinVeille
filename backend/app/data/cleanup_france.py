"""
Nettoyage des données France :
- Marquer les fiches expirées
- Supprimer les sources en doublon
- Normaliser les organismes
- Supprimer les fiches trop pauvres
Usage: docker exec kafundo-backend python -m app.data.cleanup_france
"""
import asyncio

from sqlalchemy import text

from app.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        print("=== 1. Fiches France expirées ===")
        r = await db.execute(text("""
            UPDATE devices SET status='expired', updated_at=NOW()
            WHERE country='France'
              AND close_date < NOW()
              AND status IN ('open','standby')
            RETURNING id
        """))
        expired = len(r.fetchall())
        print(f"  {expired} fiches marquées expirées")

        print("=== 2. Source doublon aide carburant ===")
        r = await db.execute(text("""
            DELETE FROM sources
            WHERE name LIKE '%aide carburant%'
              AND id NOT IN (
                SELECT MIN(id) FROM sources WHERE name LIKE '%aide carburant%'
              )
            RETURNING id
        """))
        dup_sources = len(r.fetchall())
        print(f"  {dup_sources} sources en doublon supprimées")

        print("=== 3. Normalisation organismes ===")
        norms = [
            ("BPI France", "Bpifrance"),
            ("BPI", "Bpifrance"),
            ("bpifrance", "Bpifrance"),
            ("Bpi France", "Bpifrance"),
            ("ADEME", "ADEME"),
            ("ademe", "ADEME"),
            ("Agence de la transition ecologique", "ADEME"),
        ]
        total_norm = 0
        for old, new in norms:
            r = await db.execute(text("""
                UPDATE devices SET organism=:new, updated_at=NOW()
                WHERE country='France' AND organism=:old AND organism != :new
                RETURNING id
            """), {"old": old, "new": new})
            total_norm += len(r.fetchall())
        print(f"  {total_norm} organismes normalisés")

        print("=== 4. Fiches trop pauvres ===")
        r = await db.execute(text("""
            UPDATE devices SET validation_status='pending_review', updated_at=NOW()
            WHERE country='France'
              AND validation_status = 'auto_published'
              AND length(coalesce(short_description,'')) < 30
              AND length(coalesce(full_description,'')) < 50
            RETURNING id
        """))
        thin = len(r.fetchall())
        print(f"  {thin} fiches trop pauvres -> pending_review")

        print("=== 5. Fiches institutional_project France -> admin_only ===")
        r = await db.execute(text("""
            UPDATE devices SET validation_status='admin_only', updated_at=NOW()
            WHERE country='France'
              AND device_type='institutional_project'
              AND validation_status='auto_published'
            RETURNING id
        """))
        instit = len(r.fetchall())
        print(f"  {instit} projets institutionnels -> admin_only")

        await db.commit()

        # Stats finales
        r = await db.execute(text("""
            SELECT validation_status, COUNT(*)
            FROM devices WHERE country='France'
            GROUP BY validation_status
            ORDER BY COUNT(*) DESC
        """))
        print("\n=== Bilan France ===")
        total = 0
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")
            total += row[1]
        print(f"  TOTAL: {total}")


if __name__ == "__main__":
    asyncio.run(main())
