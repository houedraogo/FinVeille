"""Traduit les titres en anglais des fiches publiées via l'IA.

Usage: docker exec kafundo-backend python app/data/translate_english_titles.py
"""
from __future__ import annotations

import asyncio
import json
import re

import httpx
from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal

EN_WORDS = re.compile(
    r'\b(the|and|for|grant|fund|programme|challenge|fellowship|call for|award|opportunity|opportunities|support|funding|access|innovation|africa|african|impact|women|youth|empowerment|business|market|trade|capacity|building|accelerat|incubat|startup|entrepreneur|competition|scholarship|apply|application|deadline|eligible|eligib)\b',
    re.IGNORECASE,
)
FR_WORDS = re.compile(
    r'\b(le|la|les|de|du|des|un|une|pour|avec|sur|dans|par|au|aux|appel|candidat|projet|aide|financement|subvention|programme|bourse|concours|prix|soutien|accompagnement|dispositif|fonds|credit|garantie)\b',
    re.IGNORECASE,
)


def is_english(title: str) -> bool:
    en = len(EN_WORDS.findall(title))
    fr = len(FR_WORDS.findall(title))
    return en >= 3 and en > fr


async def translate_title(title: str) -> str | None:
    if not settings.OPENAI_API_KEY:
        return None
    prompt = (
        f"Traduis ce titre en français professionnel et concis, sans guillemets ni explication. "
        f"Garde les noms propres et acronymes tels quels. "
        f"Titre: {title}"
    )
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Tu es un traducteur professionnel français. Tu traduis des titres de programmes de financement en français clair et concis."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 200,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    translated = data["choices"][0]["message"]["content"].strip().strip('"').strip("'")
    return translated if translated and translated.lower() != title.lower() else None


async def normalize_title(title: str) -> str:
    from unidecode import unidecode
    return re.sub(r"\s+", " ", unidecode(title.lower()).strip())


async def main():
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT id, title FROM devices
            WHERE validation_status IN ('auto_published', 'manually_published')
            ORDER BY created_at DESC
        """))).fetchall()

    english = [(r.id, r.title) for r in rows if is_english(r.title)]
    print(f"Fiches à traduire: {len(english)}")

    translated_count = 0
    failed_count = 0

    async with AsyncSessionLocal() as db:
        for fid, title in english:
            print(f"  Traduction: {title[:70]}")
            try:
                title_fr = await translate_title(title)
                if title_fr:
                    from unidecode import unidecode
                    title_norm = re.sub(r"\s+", " ", unidecode(title_fr.lower()).strip())
                    await db.execute(text("""
                        UPDATE devices
                        SET title = :title_fr, title_normalized = :title_norm, updated_at = NOW()
                        WHERE id = :id
                    """), {"title_fr": title_fr, "title_norm": title_norm, "id": fid})
                    print(f"    → {title_fr}")
                    translated_count += 1
                else:
                    print(f"    → (inchangé)")
                    failed_count += 1
            except Exception as exc:
                print(f"    Erreur: {exc}")
                failed_count += 1
            await asyncio.sleep(0.3)  # éviter rate limit

        await db.commit()

    print(f"\nRésultat: {translated_count} traduits, {failed_count} ignorés/échecs")


if __name__ == "__main__":
    asyncio.run(main())
