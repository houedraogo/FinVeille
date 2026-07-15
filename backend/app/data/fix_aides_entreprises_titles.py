"""
Fix — Corriger les titres corrompus des fiches aides-entreprises.fr.

Contexte : l'ancien code décodait le CSV en latin-1 puis en UTF-8 avec errors="replace",
remplaçant tous les caractères accentués (à, é, è, â…) par U+FFFD, ensuite converti en
apostrophe. Le source_hash fut calculé sur ce titre corrompu.

Ce script simule l'ancien pipeline pour recalculer le source_hash exact de chaque ligne
CSV, retrouve la fiche en base par ce hash, et met à jour le titre avec le texte propre.

Usage: docker exec kafundo-backend python -m app.data.fix_aides_entreprises_titles
"""
import asyncio
import csv
import hashlib
import io
import re

import httpx
from sqlalchemy import text

from app.database import AsyncSessionLocal

CSV_URL = "https://data.aides-entreprises.fr/files/aides.csv"
SOURCE_NAME = "data.aides-entreprises.fr - aides aux entreprises (CSV)"


def clean_text_new(txt: str) -> str:
    """Pipeline corrigé cp1252 — texte correct."""
    if not txt:
        return ""
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def clean_text_old(txt: str) -> str:
    """Simule l'ancien pipeline bugué latin-1→UTF-8 qui corrompait les accents."""
    if not txt:
        return ""
    # Même pipeline que l'ancien code : encode latin-1 puis décode utf-8
    b = txt.encode("latin-1", errors="ignore")
    txt = b.decode("utf-8", errors="replace")
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    # L'ancien code remplaçait explicitement U+FFFD par apostrophe
    txt = txt.replace("�", "'")
    return txt


async def main() -> None:
    print("Téléchargement du CSV...", flush=True)
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.get(CSV_URL)
        resp.raise_for_status()

    # Décoder en cp1252 comme le code corrigé le fait
    raw_cp1252 = resp.content.decode("cp1252", errors="replace")
    # Aussi décoder en latin-1 pour simuler l'ancien pipeline
    raw_latin1 = resp.content.decode("latin-1", errors="replace")

    reader_new = csv.DictReader(io.StringIO(raw_cp1252), delimiter=";", quotechar='"')
    reader_old = csv.DictReader(io.StringIO(raw_latin1), delimiter=";", quotechar='"')

    rows_new = list(reader_new)
    rows_old = list(reader_old)
    print(f"{len(rows_new)} lignes CSV", flush=True)

    async with AsyncSessionLocal() as db:
        row_s = await db.execute(text(
            "SELECT id FROM sources WHERE name = :n LIMIT 1"
        ), {"n": SOURCE_NAME})
        source_id = row_s.scalar_one_or_none()
        if not source_id:
            print("Source introuvable, arrêt.")
            return

        # Charger tous les source_hash existants de cette source
        existing = await db.execute(text(
            "SELECT source_hash, title FROM devices WHERE source_id = :sid"
        ), {"sid": str(source_id)})
        hash_to_title = {row[0]: row[1] for row in existing.fetchall()}
        print(f"{len(hash_to_title)} fiches en base pour cette source", flush=True)

        updated = not_found = already_clean = skipped = 0

        for i, (row_n, row_o) in enumerate(zip(rows_new, rows_old)):
            aid_id = (row_n.get("id_aid") or "").strip()
            if not aid_id:
                skipped += 1
                continue

            clean_t = clean_text_new(row_n.get("aid_nom") or "")
            old_t = clean_text_old(row_o.get("aid_nom") or "")

            if not clean_t or len(clean_t) < 5:
                skipped += 1
                continue

            # Si les titres sont identiques, pas de corruption sur ce titre
            if clean_t == old_t:
                already_clean += 1
                continue

            # Hash tel que l'ancien code l'aurait calculé
            old_hash = hashlib.sha256(f"{aid_id}:{old_t}".encode()).hexdigest()

            if old_hash not in hash_to_title:
                not_found += 1
                continue

            db_title = hash_to_title[old_hash]
            if db_title == clean_t:
                already_clean += 1
                continue

            result = await db.execute(text("""
                UPDATE devices
                SET title = :title,
                    title_normalized = :title_normalized,
                    updated_at = NOW()
                WHERE source_hash = :hash
                  AND source_id = :sid
            """), {
                "title": clean_t,
                "title_normalized": clean_t.lower(),
                "hash": old_hash,
                "sid": str(source_id),
            })

            if result.rowcount:
                updated += 1

            if i % 1000 == 0 and i > 0:
                await db.commit()
                print(f"  {i} traités, {updated} corrigés...", flush=True)

        await db.commit()
        print(
            f"\nTerminé : {updated} titres corrigés, "
            f"{already_clean} déjà propres, {not_found} non trouvés en base, {skipped} ignorés"
        )


if __name__ == "__main__":
    asyncio.run(main())
