import asyncio
import json
import re

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


SECTION_TITLES = (
    "Presentation",
    "Présentation",
    "Criteres d'eligibilite",
    "Critères d'éligibilité",
    "Montant / avantages",
    "Calendrier",
    "Demarche",
    "Démarche",
    "Source officielle",
    "Points a verifier",
    "Points à vérifier",
)


def repair_markdown(text: str | None) -> str:
    value = (text or "").strip()
    if not value:
        return value

    value = re.sub(r"\s+##\s+", "\n\n## ", value)
    for title in SECTION_TITLES:
        value = re.sub(rf"## {re.escape(title)}\s+", f"## {title}\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device).where(
                    Device.full_description.is_not(None),
                    Device.full_description.ilike("%##%"),
                )
            )
        ).scalars().all()

        updated = 0
        preview: list[dict] = []
        for device in devices:
            before = device.full_description or ""
            after = repair_markdown(before)
            if after != before:
                device.full_description = after
                updated += 1
                if len(preview) < 12:
                    preview.append({"title": device.title, "before": before[:160], "after": after[:180]})

        await db.commit()

    return {"updated": updated, "preview": preview}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
