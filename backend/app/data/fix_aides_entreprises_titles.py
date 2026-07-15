"""
Fix — Corriger les titres corrompus des fiches aides-entreprises.fr.

Contexte : l'ancien code décodait le CSV en latin-1 puis ré-encodait en UTF-8
avec errors="replace", ce qui remplaçait TOUS les caractères accentués (à, é, è,
â, ê, î, ô, û, ç…) par U+FFFD, ensuite converti en apostrophe '.

Ce script simule l'ancien pipeline pour calculer le slug corrompu de chaque fiche
CSV, retrouve la fiche en base par ce slug, et met à jour le titre propre.

Usage: docker exec kafundo-backend python -m app.data.fix_aides_entreprises_titles
"""
import asyncio
import csv
import io
import re

import httpx
from slugify import slugify
from sqlalchemy import text

from app.database import AsyncSessionLocal

CSV_URL = "https://data.aides-entreprises.fr/files/aides.csv"
SOURCE_NAME = "data.aides-entreprises.fr - aides aux entreprises (CSV)"


def clean_text(txt: str) -> str:
    """Pipeline corrigé — décodage cp1252 correct."""
    if not txt:
        return ""
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def corrupt_title(csv_title: str) -> str:
    """Simule l'ancien pipeline bugué latin-1→UTF-8 pour retrouver le titre corrompu."""
    try:
        b = csv_title.encode("latin-1", errors="ignore")
        result = b.decode("utf-8", errors="replace")
        result = re.sub(r"<[^>]+>", " ", result)
        result = re.sub(r"\s+", " ", result).strip()
        result = result.replace("�", "'")
        return result
    except Exception:
        return csv_title


def make_slug_from_title(title: str, aid_id: str) -> str:
    base = slugify(title, max_length=60) or f"aide-{aid_id}"
    return f"fr-ae-{base}"


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
        row_s = await db.execute(text(
            "SELECT id FROM sources WHERE name = :n LIMIT 1"
        ), {"n": SOURCE_NAME})
        source_id = row_s.scalar_one_or_none()
        if not source_id:
            print("Source introuvable, arrêt.")
            return

        updated = not_found = already_clean = 0

        for i, row in enumerate(rows):
            aid_id = (row.get("id_aid") or "").strip()
            if not aid_id:
                continue

            clean_t = clean_text(row.get("aid_nom") or "")
            if not clean_t or len(clean_t) < 5:
                continue

            corrupt_t = corrupt_title(clean_t)

            # Si les deux sont identiques, pas de corruption possible sur ce titre
            if corrupt_t == clean_t:
                already_clean += 1
                continue

            # Slug que l'ancien code aurait généré
            old_slug = make_slug_from_title(corrupt_t, aid_id)

            result = await db.execute(text("""
                UPDATE devices
                SET title = :title,
                    title_normalized = :title_normalized,
                    updated_at = NOW()
                WHERE slug = :slug
                  AND source_id = :sid
                  AND title != :title
            """), {
                "title": clean_t,
                "title_normalized": clean_t.lower(),
                "slug": old_slug,
                "sid": str(source_id),
            })

            if result.rowcount:
                updated += 1
            else:
                not_found += 1

            if i % 2000 == 0 and i > 0:
                await db.commit()
                print(f"  {i} traités, {updated} titres corrigés...", flush=True)

        await db.commit()
        print(
            f"\nTerminé : {updated} titres corrigés, "
            f"{already_clean} déjà propres, {not_found} slugs non trouvés"
        )

        # Vérification rapide
        r = await db.execute(text(
            "SELECT COUNT(*) FROM devices "
            "WHERE source_id = :sid AND title LIKE '%''%'",
        ), {"sid": str(source_id)})
        print(f"Fiches encore avec apostrophe dans le titre : {r.scalar()}")


if __name__ == "__main__":
    asyncio.run(main())
