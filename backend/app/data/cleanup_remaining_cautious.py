from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import clean_editorial_text


DATA_AIDES_SOURCE = "data.aides-entreprises.fr - aides aux entreprises"
GLOBAL_SOUTH_SOURCE = "Global South Opportunities - Funding"


def _append_once(text: str | None, addition: str, max_len: int = 700) -> str:
    current = clean_editorial_text(text or "")
    if addition.lower() in current.lower():
        return current[:max_len].rstrip()
    if not current:
        return addition[:max_len].rstrip()
    separator = "" if current.endswith((".", "!", "?")) else "."
    return f"{current}{separator} {addition}"[:max_len].rstrip()


def _compact_long_text(text: str | None, max_len: int = 5600) -> str | None:
    cleaned = clean_editorial_text(text or "")
    if not cleaned:
        return None
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[:max_len].rsplit(" ", 1)[0].rstrip()
    return f"{cut}."


def _fallback_sections(device: Device) -> list[dict]:
    return [
        {
            "key": "presentation",
            "title": "Présentation",
            "content": clean_editorial_text(device.short_description or device.title or ""),
            "confidence": 75,
            "source": "cleanup_remaining_cautious",
        },
        {
            "key": "eligibility",
            "title": "Critères d'éligibilité",
            "content": clean_editorial_text(
                device.eligibility_criteria
                or "Les critères détaillés doivent être confirmés sur la source officielle."
            ),
            "confidence": 65,
            "source": "cleanup_remaining_cautious",
        },
        {
            "key": "funding",
            "title": "Montant / avantages",
            "content": clean_editorial_text(
                device.funding_details
                or "Le montant exact ou les avantages associés doivent être confirmés sur la source officielle."
            ),
            "confidence": 60,
            "source": "cleanup_remaining_cautious",
        },
        {
            "key": "calendar",
            "title": "Calendrier",
            "content": (
                f"Date limite identifiée : {device.close_date.strftime('%d/%m/%Y')}."
                if device.close_date
                else "La source ne publie pas de date limite exploitable à ce stade."
            ),
            "confidence": 70,
            "source": "cleanup_remaining_cautious",
        },
    ]


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        sources = (
            await db.execute(select(Source).where(Source.name.in_([DATA_AIDES_SOURCE, GLOBAL_SOUTH_SOURCE])))
        ).scalars().all()
        source_by_name = {source.name: source for source in sources}

        stats = {
            "data_aides_scanned": 0,
            "data_aides_explained_standby": 0,
            "data_aides_shortened": 0,
            "global_south_scanned": 0,
            "global_south_completed": 0,
        }

        data_source = source_by_name.get(DATA_AIDES_SOURCE)
        if data_source:
            devices = (
                await db.execute(
                    select(Device).where(
                        Device.source_id == data_source.id,
                        Device.validation_status != "rejected",
                        Device.status == "standby",
                    )
                )
            ).scalars().all()
            stats["data_aides_scanned"] = len(devices)
            note = (
                "La date limite non communiquee par la source officielle doit etre confirmee avant de prioriser cette opportunite."
            )
            for device in devices:
                before_notes = device.recurrence_notes or ""
                device.recurrence_notes = _append_once(before_notes, note, max_len=500)
                device.short_description = _append_once(device.short_description, note, max_len=520)
                device.full_description = _compact_long_text(device.full_description)
                if device.full_description and len(device.full_description) <= 5601:
                    stats["data_aides_shortened"] += 1
                if note.lower() not in before_notes.lower():
                    stats["data_aides_explained_standby"] += 1

        gs_source = source_by_name.get(GLOBAL_SOUTH_SOURCE)
        if gs_source:
            devices = (
                await db.execute(
                    select(Device).where(
                        Device.source_id == gs_source.id,
                        Device.validation_status != "rejected",
                    )
                )
            ).scalars().all()
            stats["global_south_scanned"] = len(devices)
            for device in devices:
                changed = False
                if not device.funding_details or len(clean_editorial_text(device.funding_details)) < 80:
                    device.funding_details = (
                        "Le montant exact ou les avantages associés doivent être confirmés sur la source officielle. "
                        "La fiche peut mentionner un financement, un prix, un accompagnement ou une visibilité selon le programme."
                    )
                    changed = True
                if device.device_type in {"autre", "", None}:
                    title = (device.title or "").lower()
                    if any(word in title for word in ["grant", "subvention", "funding"]):
                        device.device_type = "subvention"
                    elif any(word in title for word in ["prize", "challenge", "competition"]):
                        device.device_type = "concours"
                    else:
                        device.device_type = "aap"
                    changed = True
                if device.status == "standby":
                    note = (
                        "Date limite non communiquee par la source officielle. "
                        "La source relayee ne publie pas de date limite exploitable dans la fiche actuelle."
                    )
                    device.recurrence_notes = _append_once(device.recurrence_notes, note, max_len=500)
                    device.short_description = _append_once(device.short_description, note, max_len=520)
                    changed = True
                if not device.ai_rewritten_sections_json:
                    device.ai_rewritten_sections_json = _fallback_sections(device)
                    device.ai_rewrite_status = "done"
                    device.ai_rewrite_model = "local-cleanup-remaining-cautious-v1"
                    changed = True
                if changed:
                    stats["global_south_completed"] += 1

        await db.commit()
        return stats


def main() -> None:
    import json

    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
