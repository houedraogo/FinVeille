from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import clean_editorial_text


SOURCE_NAME = "data.aides-entreprises.fr - aides aux entreprises"


def _append_note(text: str | None, addition: str) -> str:
    current = clean_editorial_text(text or "")
    if addition.lower() in current.lower():
        return current
    if not current:
        return addition
    separator = "" if current.endswith((".", "!", "?")) else "."
    return f"{current}{separator} {addition}".strip()


def _refresh_summary(device: Device) -> None:
    summary = clean_editorial_text(device.short_description or "")
    if not summary:
        summary = clean_editorial_text(device.title or "Cette opportunité")

    if device.status == "expired" and device.close_date:
        note = f"La période connue s'est terminée le {device.close_date.strftime('%d/%m/%Y')}."
        summary = _append_note(summary, note)
    elif device.status == "open" and device.close_date:
        note = f"La date limite actuellement identifiée est le {device.close_date.strftime('%d/%m/%Y')}."
        summary = _append_note(summary, note)
    elif device.status == "recurring":
        note = "Cette opportunité fonctionne comme une offre permanente ou mobilisable sans date limite unique publiée."
        summary = _append_note(summary, note)
    elif device.status == "standby":
        note = "La date limite n'est pas communiquée clairement par la source officielle."
        summary = _append_note(summary, note)

    device.short_description = summary[:520].rstrip()


async def run() -> dict:
    today = date.today()
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        devices = (
            await db.execute(
                select(Device).where(
                    Device.source_id == source.id,
                    Device.validation_status != "rejected",
                )
            )
        ).scalars().all()

        stats = {
            "scanned": len(devices),
            "to_expired": 0,
            "to_open": 0,
            "to_recurring": 0,
            "standby_explained": 0,
            "updated": 0,
        }
        preview: list[dict] = []

        for device in devices:
            before = (device.status, device.is_recurring, device.recurrence_notes)
            new_status = device.status

            if device.close_date:
                if device.close_date < today:
                    new_status = "expired"
                    device.is_recurring = False
                    device.recurrence_notes = None
                else:
                    new_status = "open"
                    device.is_recurring = False
                    device.recurrence_notes = None
            elif device.is_recurring or device.status == "recurring":
                new_status = "recurring"
                device.is_recurring = True
                device.recurrence_notes = (
                    "Dispositif permanent ou mobilisable sans date limite unique communiquée par la source officielle."
                )
            elif device.status == "standby":
                device.recurrence_notes = (
                    "Date limite non communiquee par la source officielle. La fiche reste a verifier avant toute decision."
                )

            device.status = new_status
            _refresh_summary(device)

            after = (device.status, device.is_recurring, device.recurrence_notes)
            if before == after:
                continue

            stats["updated"] += 1
            if device.status == "expired":
                stats["to_expired"] += 1
            elif device.status == "open":
                stats["to_open"] += 1
            elif device.status == "recurring":
                stats["to_recurring"] += 1
            elif device.status == "standby":
                stats["standby_explained"] += 1

            if len(preview) < 25:
                preview.append(
                    {
                        "title": device.title,
                        "before_status": before[0],
                        "after_status": device.status,
                        "close_date": str(device.close_date) if device.close_date else None,
                        "is_recurring": device.is_recurring,
                    }
                )

        await db.commit()

    return {"source": SOURCE_NAME, "stats": stats, "preview": preview}


def main() -> None:
    import json

    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
