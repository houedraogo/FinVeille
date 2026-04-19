import argparse
import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import has_recurrence_evidence, sanitize_text


def _build_text_blob(device: Device) -> str:
    parts = [
        device.title or "",
        device.short_description or "",
        device.full_description or "",
        device.source_raw or "",
    ]
    return sanitize_text(" ".join(part for part in parts if part))


async def run_backfill(source_name: str, dry_run: bool = False) -> dict:
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == source_name))).scalar_one_or_none()
        if not source:
            raise RuntimeError(f"Source introuvable: {source_name}")

        config = source.config or {}
        default_recurring = bool(config.get("assume_recurring_without_close_date"))
        if "data.aides-entreprises.fr" in source.name.lower():
            default_recurring = True
        default_standby = (
            bool(config.get("assume_standby_without_close_date"))
            or "les-aides.fr" in source.name.lower()
            or "banque des territoires" in source.name.lower()
        )
        query = select(Device).where(
            Device.source_id == source.id,
            Device.status == "open",
            Device.close_date.is_(None),
        )
        devices = (await db.execute(query)).scalars().all()

        recurring = 0
        standby = 0
        preview = []

        for device in devices:
            text_blob = _build_text_blob(device)
            if has_recurrence_evidence(text_blob):
                next_status = "recurring"
                next_recurrence = (
                    "Classe automatiquement comme dispositif recurrent: "
                    "le texte source indique un fonctionnement sans fenetre de cloture unique."
                )
            elif default_recurring:
                next_status = "recurring"
                next_recurrence = (
                    "Classe automatiquement comme dispositif recurrent: "
                    "la source n'expose pas de date de cloture fiable."
                )
            elif default_standby:
                next_status = "standby"
                next_recurrence = device.recurrence_notes
            else:
                continue

            if len(preview) < 8:
                preview.append({"title": device.title, "from": device.status, "to": next_status})

            if not dry_run:
                device.status = next_status
                device.is_recurring = next_status == "recurring"
                device.recurrence_notes = next_recurrence

            if next_status == "recurring":
                recurring += 1
            else:
                standby += 1

        if not dry_run:
            await db.commit()

        return {
            "source": source.name,
            "matched": len(devices),
            "recurring": recurring,
            "standby": standby,
            "preview": preview,
            "dry_run": dry_run,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(run_backfill(args.source_name, dry_run=args.dry_run))
    print(result)


if __name__ == "__main__":
    main()
