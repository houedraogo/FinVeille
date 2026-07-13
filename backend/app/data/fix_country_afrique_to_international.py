"""
Fix 7 — Affiner le label pays "Afrique" (trop vague pour le matching).

Contexte : 142 fiches avaient country='Afrique' — un label continental trop large
pour le moteur de matching qui travaille par pays. Ces fiches provenaient de sources
pan-africaines (VC4A, Opportunities For Africans, AECF, etc.) qui couvrent plusieurs
pays simultanément.

Action :
  - country 'Afrique' → 'International' (scope multi-pays correct)
  - region conservée ou définie à 'Afrique' pour maintenir le filtre continental

Usage: docker exec kafundo-backend python -m app.data.fix_country_afrique_to_international
"""
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            UPDATE devices
            SET country = 'International',
                region = COALESCE(NULLIF(region, ''), 'Afrique'),
                updated_at = NOW()
            WHERE country = 'Afrique'
        """))
        count = result.rowcount
        await db.commit()
        print(f"Fiches mises à jour : {count}")

        row = await db.execute(text("SELECT COUNT(*) FROM devices WHERE country = 'Afrique'"))
        print(f"Fiches country='Afrique' restantes : {row.scalar()}")

        row = await db.execute(text(
            "SELECT COUNT(*) FROM devices WHERE country='International' AND region='Afrique'"
        ))
        print(f"Fiches International+région Afrique : {row.scalar()}")


if __name__ == "__main__":
    asyncio.run(main())
