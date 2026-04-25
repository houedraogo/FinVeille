import argparse
import asyncio
import json
from datetime import date
from typing import Any

from sqlalchemy import select
from unidecode import unidecode

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.services.deadline_classifier import classify_deadline
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import compute_completeness, has_recurrence_evidence, sanitize_text


UNKNOWN_DEADLINE_NOTE = "Date limite non communiquee par la source: verification manuelle requise."


def _text_blob(device: Device) -> str:
    return sanitize_text(
        " ".join(
            value or ""
            for value in (
                device.title,
                device.short_description,
                device.full_description,
                device.eligibility_criteria,
                device.funding_details,
                device.recurrence_notes,
                device.source_raw,
            )
        )
    )


def _has_unknown_deadline_signal(text: str) -> bool:
    sample = f" {unidecode(text.lower())} "
    return any(
        marker in sample
        for marker in (
            " cloture non communiquee ",
            " date limite non communiquee ",
            " sans date limite communiquee ",
            " calendrier non communique ",
            " deadline not specified ",
        )
    )


def _apply_quality_gate(device: Device) -> list[str]:
    changed: list[str] = []
    payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
    decision = DeviceQualityGate().evaluate(payload)
    tags = set(device.tags or [])
    tags.update(f"quality:{reason}" for reason in decision.reasons)

    if device.validation_status != decision.validation_status:
        device.validation_status = decision.validation_status
        changed.append("validation_status")
    if sorted(tags) != (device.tags or []):
        device.tags = sorted(tags)
        changed.append("tags")
    return changed


def _fix_device(device: Device) -> list[str]:
    changed: list[str] = []
    text_blob = _text_blob(device)
    payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
    deadline = classify_deadline(payload)
    tags = set(device.tags or [])
    old_deadline_tags = {tag for tag in tags if tag.startswith("deadline:")}
    tags.difference_update(old_deadline_tags)
    tags.add(deadline.tag)
    if sorted(tags) != (device.tags or []):
        device.tags = sorted(tags)
        changed.append("tags")

    if device.close_date and device.close_date < date.today() and device.status != "expired":
        device.status = "expired"
        device.is_recurring = False
        changed.extend(["status", "is_recurring"])

    if device.status in {"open", "unknown"} and not device.close_date:
        if has_recurrence_evidence(text_blob) and not _has_unknown_deadline_signal(text_blob):
            device.status = "recurring"
            device.is_recurring = True
            device.recurrence_notes = device.recurrence_notes or (
                "Classe comme dispositif recurrent: la source indique un fonctionnement sans fenetre de cloture unique."
            )
            changed.extend(["status", "is_recurring", "recurrence_notes"])
        else:
            device.status = "standby"
            device.is_recurring = False
            if device.validation_status != "pending_review":
                device.validation_status = "pending_review"
                changed.append("validation_status")
            tags = set(device.tags or [])
            tags.add("quality:unknown_deadline")
            device.tags = sorted(tags)
            device.recurrence_notes = device.recurrence_notes or UNKNOWN_DEADLINE_NOTE
            changed.extend(["status", "is_recurring", "tags", "recurrence_notes"])

    if device.status == "recurring" and device.close_date and device.close_date < date.today():
        device.status = "expired"
        device.is_recurring = False
        changed.extend(["status", "is_recurring"])

    if not device.close_date:
        if deadline.status and device.status != deadline.status:
            device.status = deadline.status
            changed.append("status")
        if deadline.is_recurring is not None and device.is_recurring != deadline.is_recurring:
            device.is_recurring = deadline.is_recurring
            changed.append("is_recurring")
        if deadline.validation_status and device.validation_status != deadline.validation_status:
            device.validation_status = deadline.validation_status
            changed.append("validation_status")
        if device.recurrence_notes != deadline.note:
            device.recurrence_notes = deadline.note
            changed.append("recurrence_notes")

    changed.extend(_apply_quality_gate(device))
    if changed:
        payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
        device.completeness_score = compute_completeness(payload)
    return sorted(set(changed))


async def run(*, apply: bool = False, limit: int | None = None) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        query = (
            select(Device)
            .where(Device.validation_status != "rejected")
            .order_by(Device.updated_at.desc().nullslast())
        )
        if limit:
            query = query.limit(limit)
        devices = (await db.execute(query)).scalars().all()

        stats = {
            "scanned": len(devices),
            "expired_fixed": 0,
            "recurring_fixed": 0,
            "unknown_deadline_fixed": 0,
            "quality_updated": 0,
        }
        preview = []

        with db.no_autoflush:
            for device in devices:
                before = {
                    "status": device.status,
                    "validation_status": device.validation_status,
                    "is_recurring": device.is_recurring,
                    "tags": list(device.tags or []),
                }
                if apply:
                    changed = _fix_device(device)
                    after_status = device.status
                    after_validation = device.validation_status
                else:
                    clone = type("DevicePreview", (), {})()
                    for column in Device.__table__.columns:
                        setattr(clone, column.name, getattr(device, column.name))
                    changed = _fix_device(clone)  # type: ignore[arg-type]
                    after_status = getattr(clone, "status", device.status)
                    after_validation = getattr(clone, "validation_status", device.validation_status)

                if not changed:
                    continue
                if before["status"] != after_status:
                    if after_status == "expired":
                        stats["expired_fixed"] += 1
                    elif after_status == "recurring":
                        stats["recurring_fixed"] += 1
                    elif after_status == "standby":
                        stats["unknown_deadline_fixed"] += 1
                if before["validation_status"] != after_validation:
                    stats["quality_updated"] += 1
                if len(preview) < 12:
                    preview.append(
                        {
                            "title": device.title,
                            "from": before,
                            "to": {"status": after_status, "validation_status": after_validation},
                            "changed": changed,
                        }
                    )

        if apply:
            await db.commit()
        else:
            await db.rollback()

        return {"dry_run": not apply, "stats": stats, "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fiabilise les dates, statuts et quality gates du catalogue.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
