from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


FIXES = {
    "12d4ac77-cd0e-41ab-86b9-cf184097806d": {
        "short_description": (
            "Ancienne fiche AECF rejetée car issue d'une extraction trop large de la page d'accueil. "
            "La vraie opportunité AECF sur l'entrepreneuriat féminin au Bénin et au Burkina Faso est "
            "déjà représentée par une fiche dédiée plus complète."
        ),
        "full_description": (
            "## Note de nettoyage\n"
            "Cette entrée provenait d'une collecte trop générique de la page d'accueil AECF. "
            "Elle reste rejetée pour éviter les doublons et le bruit dans le catalogue public.\n\n"
            "## Fiche de référence\n"
            "La version exploitable est la fiche AECF dédiée à l'entrepreneuriat féminin pour une économie "
            "plus verte au Bénin et au Burkina Faso."
        ),
    },
    "711c3fdb-1fb5-45b8-89ad-dd7421eea2bc": {
        "short_description": (
            "Ancienne fiche AECF rejetée car le contenu correspondait à un slogan institutionnel et non à "
            "une opportunité de financement exploitable. Elle est conservée uniquement comme trace de nettoyage."
        ),
        "full_description": (
            "## Note de nettoyage\n"
            "Cette entrée ne décrit pas un appel, une compétition ou un financement précis. "
            "Elle reste rejetée afin de ne pas polluer les résultats utilisateur avec du contenu institutionnel."
        ),
    },
    "16784a81-d1bf-4159-9b85-e5c13ec4be2a": {
        "short_description": (
            "Ancienne fiche AECF rejetée car elle correspond à une actualité ou un atelier institutionnel, "
            "pas à une opportunité de financement directement actionnable pour les utilisateurs."
        ),
        "full_description": (
            "## Note de nettoyage\n"
            "Cette entrée AECF-WHO regional workshop relève d'une actualité institutionnelle. "
            "Elle reste rejetée car elle ne contient pas de calendrier, montant, critères ou démarche "
            "suffisamment exploitables pour une candidature."
        ),
    },
}


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        updated = 0
        preview = []
        for device_id, values in FIXES.items():
            device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one_or_none()
            if device is None:
                continue
            device.short_description = values["short_description"]
            device.full_description = values["full_description"]
            device.eligibility_criteria = (
                "Non applicable : fiche rejetée car le contenu ne correspond pas à une opportunité de financement exploitable."
            )
            device.funding_details = (
                "Non applicable : aucun montant ou avantage financier exploitable n'est associé à cette entrée rejetée."
            )
            device.content_sections_json = [
                {
                    "key": "cleanup_note",
                    "title": "Note de nettoyage",
                    "content": values["short_description"],
                    "confidence": 95,
                    "source": "manual_cleanup",
                }
            ]
            updated += 1
            preview.append({"id": device_id, "title": device.title, "validation_status": device.validation_status})

        await db.commit()

    return {"updated": updated, "preview": preview}


def main() -> None:
    import json

    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
