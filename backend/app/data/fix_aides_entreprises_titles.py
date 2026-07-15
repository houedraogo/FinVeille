"""
Fix — Corriger les titres corrompus des fiches aides-entreprises.fr.

Contexte : le CSV était décodé en latin-1 au lieu de cp1252. Les caractères accentués
français (à, é, è, â, ê, î, ô, û, ç…) ont été corrompus en apostrophes ou caractères
de remplacement lors du premier import. Le champ ON CONFLICT ne corrigeait pas les titres
déjà stockés car les slugs différaient.

Mécanisme de lookup : la colonne source_url stocke l'URL canonique avec l'aid_id,
ce qui permet de retrouver chaque fiche sans dépendre du titre ou du slug corrompu.

Usage: docker exec kafundo-backend python -m app.data.fix_aides_entreprises_titles
"""
import asyncio
import csv
import io
import re

import httpx
from sqlalchemy import text

from app.database import AsyncSessionLocal

CSV_URL = "https://data.aides-entreprises.fr/files/aides.csv"
SOURCE_NAME = "data.aides-entreprises.fr - aides aux entreprises (CSV)"


def clean_text(txt: str) -> str:
    if not txt:
        return ""
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


async def main() -> None:
    print("Téléchargement du CSV...", flush=True)
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.get(CSV_URL)
        resp.raise_for_status()

    raw = resp.content.decode("cp1252", errors="replace")
    reader = csv.DictReader(io.StringIO(raw), delimiter=";", quotechar='"')
    rows = list(reader)
    print(f"{len(rows)} lignes CSV", flush=True)

    async with AsyncSessionLocal() as db:
        # Récupérer source_id
        row_s = await db.execute(text(
            "SELECT id FROM sources WHERE name = :n LIMIT 1"
        ), {"n": SOURCE_NAME})
        source_id = row_s.scalar_one_or_none()
        if not source_id:
            print("Source introuvable, arrêt.")
            return

        updated = skipped = errors = 0

        for i, row in enumerate(rows):
            try:
                aid_id = (row.get("id_aid") or "").strip()
                if not aid_id:
                    skipped += 1
                    continue

                clean_title = clean_text(row.get("aid_nom") or "")
                if not clean_title or len(clean_title) < 5:
                    skipped += 1
                    continue

                canonical_url = f"https://www.aides-entreprises.fr/aide/{aid_id}"

                result = await db.execute(text("""
                    UPDATE devices
                    SET title = :title,
                        title_normalized = :title_normalized,
                        updated_at = NOW()
                    WHERE source_id = :sid
                      AND source_url = :url
                      AND title != :title
                """), {
                    "title": clean_title,
                    "title_normalized": clean_title.lower(),
                    "sid": str(source_id),
                    "url": canonical_url,
                })

                if result.rowcount:
                    updated += 1

                if i % 2000 == 0 and i > 0:
                    await db.commit()
                    print(f"  {i} traités, {updated} titres corrigés...", flush=True)

            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  ERR ligne {i}: {e}", flush=True)

        await db.commit()
        print(f"\nTerminé : {updated} titres corrigés, {skipped} ignorés, {errors} erreurs")


if __name__ == "__main__":
    asyncio.run(main())
