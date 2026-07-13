"""
Fix 4 — Normaliser les labels ai_readiness_label non-standard.

Contexte : 15 fiches avaient des labels comme "Prête pour recommandation" (texte libre)
ou "pret_recommandation" (slug raccourci) au lieu des 4 valeurs canoniques :
  - pret_pour_recommandation_ia
  - utilisable_avec_prudence
  - a_verifier
  - non_exploitable

Ces labels non-standard empêchaient le filtrage et l'affichage correct dans l'UI.

Usage: docker exec kafundo-backend python -m app.data.fix_normalize_ai_readiness_labels
"""
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal

LABEL_FIXES = [
    ("Prête pour recommandation", "pret_pour_recommandation_ia"),
    ("pret_recommandation", "pret_pour_recommandation_ia"),
    ("A verifier avant recommandation", "a_verifier"),
    ("a verifier", "a_verifier"),
    ("non exploitable", "non_exploitable"),
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        total = 0
        for old, new in LABEL_FIXES:
            result = await db.execute(text(
                "UPDATE devices SET ai_readiness_label = :new WHERE ai_readiness_label = :old"
            ), {"new": new, "old": old})
            if result.rowcount:
                print(f"  '{old}' → '{new}' : {result.rowcount} fiches")
                total += result.rowcount
        await db.commit()
        print(f"Total normalisés : {total}")

        rows = await db.execute(text(
            "SELECT DISTINCT ai_readiness_label FROM devices "
            "WHERE ai_readiness_label IS NOT NULL ORDER BY 1"
        ))
        print("Labels actifs :")
        for (label,) in rows.fetchall():
            print(f"  {label}")


if __name__ == "__main__":
    asyncio.run(main())
