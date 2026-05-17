from __future__ import annotations

import asyncio
import json
from datetime import date

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device


PUBLIC_STATUSES = {"auto_published", "approved", "validated"}


def _is_public(device: Device) -> bool:
    return device.validation_status in PUBLIC_STATUSES and device.status in {"open", "recurring"}


def _flags(device: Device) -> list[str]:
    today = date.today()
    flags: list[str] = []
    if device.status == "open" and device.close_date and device.close_date < today:
        flags.append("open_date_passee")
    if device.status == "open" and not device.close_date:
        flags.append("open_sans_date")
    if device.device_type in {"autre", "institutional_project"}:
        flags.append("type_non_actionnable")
    if not device.source_url:
        flags.append("source_absente")
    if len((device.short_description or "").strip()) < 140 and len((device.full_description or "").strip()) < 250:
        flags.append("texte_faible")
    if not (device.eligibility_criteria or "").strip():
        flags.append("criteres_absents")
    if not (device.funding_details or "").strip():
        flags.append("montant_absent")
    return flags


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .where(Device.country.in_(["Burkina Faso", "Afrique de l'Ouest", "Afrique"]))
                .where(
                    (Device.title.ilike("%Burkina%"))
                    | (Device.country == "Burkina Faso")
                    | (Device.region.ilike("%Burkina%"))
                    | (Device.zone.ilike("%Burkina%"))
                    | (Device.short_description.ilike("%Burkina%"))
                    | (Device.full_description.ilike("%Burkina%"))
                )
                .order_by(Device.validation_status.asc(), Device.status.asc(), Device.close_date.asc().nullslast())
            )
        ).scalars().all()

        rows = []
        for device in devices:
            flags = _flags(device)
            rows.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "organism": device.organism,
                    "country": device.country,
                    "type": device.device_type,
                    "status": device.status,
                    "validation_status": device.validation_status,
                    "close_date": device.close_date.isoformat() if device.close_date else None,
                    "public_visible": _is_public(device),
                    "flags": flags,
                    "source_url": device.source_url,
                }
            )

        public_rows = [row for row in rows if row["public_visible"]]
        return {
            "total": len(rows),
            "public_visible": len(public_rows),
            "admin_only_or_other": len(rows) - len(public_rows),
            "public_with_flags": sum(1 for row in public_rows if row["flags"]),
            "flag_counts": {
                flag: sum(1 for row in public_rows if flag in row["flags"])
                for flag in sorted({flag for row in public_rows for flag in row["flags"]})
            },
            "public_rows": public_rows,
            "all_flagged_public_rows": [row for row in public_rows if row["flags"]],
        }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
