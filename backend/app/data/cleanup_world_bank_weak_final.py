import asyncio

from sqlalchemy import func, or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import clean_editorial_text, compute_completeness


def _country_phrase(country: str) -> str:
    cleaned = clean_editorial_text(country or "")
    if not cleaned:
        return "dans le pays cible"
    lowered = cleaned.lower()
    if lowered in {"madagascar"}:
        return f"a {cleaned}"
    if lowered in {"tunisie", "guinee", "mauritanie", "ethiopie", "cote d'ivoire"}:
        return f"en {cleaned}"
    return f"au {cleaned}"


def _long_summary(device: Device, source: Source) -> str:
    country = clean_editorial_text(device.country or source.country or "")
    title = clean_editorial_text(device.title or "Ce projet")
    parts = [
        f"{title} est un projet institutionnel de la Banque mondiale porte {_country_phrase(country)}.",
        "Cette fiche ne correspond pas a un appel a candidatures classique, mais au suivi d'une operation publique et de ses jalons officiels.",
    ]
    if device.close_date:
        parts.append(f"La cloture previsionnelle actuellement reperee est le {device.close_date.strftime('%d/%m/%Y')}.")
    if device.open_date:
        parts.append(f"La date d'ouverture enregistree est le {device.open_date.strftime('%d/%m/%Y')}.")
    if device.sectors:
        parts.append("Les secteurs principalement rattaches a cette fiche sont : " + ", ".join(clean_editorial_text(s) for s in device.sectors if clean_editorial_text(s)) + ".")
    else:
        parts.append("Le secteur detaille n'est pas explicite dans le flux stocke et doit etre confirme sur la page officielle du projet.")
    parts.append("Les conditions operationnelles, partenaires et informations de mise en oeuvre doivent etre verifies sur la source officielle de la Banque mondiale.")
    return " ".join(part.strip() for part in parts if part).strip()[:500]


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Device, Source)
                .join(Source, Source.id == Device.source_id)
                .where(
                    or_(
                        Device.organism.ilike("%World Bank%"),
                        Source.organism.ilike("%World Bank%"),
                        Source.name.ilike("%Banque Mondiale%"),
                    ),
                    or_(
                        Device.short_description.is_(None),
                        func.length(func.trim(func.coalesce(Device.short_description, ""))) < 120,
                    ),
                )
                .order_by(Source.name.asc(), Device.title.asc())
            )
        ).all()

        updated = 0
        preview: list[dict] = []

        for device, source in rows:
            summary = _long_summary(device, source)
            if summary != (device.short_description or ""):
                device.short_description = summary
                payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
                device.completeness_score = compute_completeness(payload)
                updated += 1
                preview.append(
                    {
                        "source": source.name,
                        "title": device.title,
                        "short_description": summary,
                    }
                )

        await db.commit()
        return {"updated": updated, "preview": preview}


def main() -> None:
    result = asyncio.run(run())
    print(result)


if __name__ == "__main__":
    main()
