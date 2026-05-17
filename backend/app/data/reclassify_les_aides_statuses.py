import argparse
import asyncio
import json
from collections import Counter
from datetime import date

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import has_recurrence_evidence, sanitize_text


SOURCE_NAME = "les-aides.fr - solutions de financement entreprises"


def _text_blob(device: Device) -> str:
    return sanitize_text(
        " ".join(
            part
            for part in (
                device.title,
                device.short_description,
                device.full_description,
                device.eligibility_criteria,
                device.funding_details,
                device.source_raw,
            )
            if part
        )
    )


def _target_status(device: Device) -> tuple[str, bool, str | None]:
    if device.close_date:
        if device.close_date < date.today():
            return "expired", False, None
        return "open", False, None

    if device.status in {"expired", "closed"}:
        return "expired", False, None

    if has_recurrence_evidence(_text_blob(device)):
        return (
            "recurring",
            True,
            "Classe comme financement permanent ou recurrent : la source indique un fonctionnement sans date limite unique.",
        )

    return (
        "standby",
        False,
        "Date limite non communiquee par la source : verification manuelle conseillee avant recommandation.",
    )


async def run(apply: bool = False, limit: int | None = None) -> dict:
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        query = (
            select(Device)
            .where(Device.source_id == source.id, Device.validation_status != "rejected")
            .order_by(Device.updated_at.desc().nullslast())
        )
        if limit:
            query = query.limit(limit)

        devices = (await db.execute(query)).scalars().all()
        transitions: Counter[str] = Counter()
        validation_transitions: Counter[str] = Counter()
        preview: list[dict] = []
        updated = 0

        for device in devices:
            before_status = device.status
            before_validation = device.validation_status
            next_status, next_recurring, next_note = _target_status(device)

            changed = False
            if device.status != next_status:
                device.status = next_status
                changed = True
            if bool(device.is_recurring) != next_recurring:
                device.is_recurring = next_recurring
                changed = True
            if next_note != device.recurrence_notes:
                device.recurrence_notes = next_note
                changed = True

            # Une fiche sans date ni preuve de recurrence ne doit pas etre publiee comme une opportunite sure.
            if next_status == "standby" and device.validation_status == "auto_published":
                device.validation_status = "admin_only"
                tags = list(device.tags or [])
                for tag in ["source:les_aides_admin_only", "visibility:admin_only", "quality:missing_reliable_deadline"]:
                    if tag not in tags:
                        tags.append(tag)
                device.tags = sorted(tags)
                analysis = dict(device.decision_analysis or {})
                analysis["public_visibility"] = "admin_only"
                analysis["admin_only_reason"] = "les-aides.fr: date limite non communiquee ou non exploitable"
                device.decision_analysis = analysis
                changed = True

            if next_status in {"open", "recurring", "expired"} and device.validation_status == "pending_review":
                device.validation_status = "auto_published"
                changed = True

            if changed:
                updated += 1
                transitions[f"{before_status or 'unknown'} -> {device.status}"] += 1
                validation_transitions[f"{before_validation or 'unknown'} -> {device.validation_status}"] += 1
                if len(preview) < 12:
                    preview.append(
                        {
                            "title": device.title,
                            "close_date": str(device.close_date) if device.close_date else None,
                            "status": f"{before_status} -> {device.status}",
                            "validation": f"{before_validation} -> {device.validation_status}",
                        }
                    )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {
        "dry_run": not apply,
        "source": SOURCE_NAME,
        "total_scanned": len(devices),
        "updated": updated,
        "status_transitions": dict(transitions),
        "validation_transitions": dict(validation_transitions),
        "preview": preview,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Reclasse les statuts decisionnels des fiches les-aides.fr.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
