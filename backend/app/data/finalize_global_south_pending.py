from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


EXPIRED = {
    UUID("d4792ef7-d825-4315-80d4-77604a21971c"): date(2026, 5, 8),
    UUID("dc7d2aca-a66c-4236-b145-947fdf1ab089"): date(2026, 4, 30),
    UUID("2a775cee-272f-4e21-8e6a-0193c4ed64b3"): date(2026, 5, 8),
    UUID("6bc26c14-0ace-440f-882a-f6b3dc1f7e9e"): date(2026, 5, 9),
    UUID("a63bbb57-a9ef-4ce2-bffe-c00b8812cbab"): date(2026, 5, 2),
    UUID("f21804d4-93b5-4e7c-8889-e9b493ce3aee"): date(2026, 5, 15),
    UUID("f49b210c-27de-4e89-8ea7-6a2d14ef328f"): date(2026, 5, 5),
    UUID("65556a61-dfc4-48dd-82cc-9205dbf1356a"): date(2026, 5, 15),
    UUID("b4c54e38-c1f9-4f59-a0ed-94a4132f79ad"): date(2026, 5, 13),
    UUID("83c876df-c27b-4138-be78-a5dff39475c3"): date(2025, 4, 7),
    UUID("e750818d-149f-4e3f-b069-53d72fa5b5a7"): date(2026, 4, 15),
}

FUTURE_ADMIN_ONLY = {
    UUID("e10b4fb1-10b5-46a1-9832-6595cc0e1140"): date(2026, 6, 12),
    UUID("f85a9a31-5238-4faa-978e-b311d037d61a"): date(2026, 6, 23),
    UUID("4bc37c7f-7190-4987-bce4-17ece5889999"): date(2026, 5, 31),
    UUID("37596a4d-4783-42a8-b06f-ac8983d5726c"): date(2026, 6, 8),
    UUID("a5753791-fbe6-484a-95ef-d68461437e24"): date(2026, 5, 29),
    UUID("2214e0f3-42d8-425f-8d8c-018c30d24b4b"): date(2026, 6, 30),
    UUID("c8e8390e-8222-45fa-bab6-5a494788091c"): date(2026, 7, 12),
    UUID("55651862-8425-4fa1-a021-d81cbb45130e"): date(2026, 6, 17),
    UUID("57915c78-0026-4011-9f50-c32455756e22"): date(2026, 5, 17),
    UUID("27b5d4f8-7136-425e-a3f4-02f807f2191c"): date(2026, 7, 29),
}

RECURRING_ADMIN_ONLY = {
    UUID("0928a815-bb14-4c04-a02f-39a1318f36db"),
    UUID("3ece87f3-bda5-4154-84e2-872ad2b46889"),
}


def _append_tags(device: Device, *new_tags: str) -> None:
    tags = list(device.tags or [])
    for tag in new_tags:
        if tag not in tags:
            tags.append(tag)
    device.tags = tags


async def run(dry_run: bool = True) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(
                select(Source).where(Source.name == "Global South Opportunities - Funding")
            )
        ).scalar_one()
        devices = (
            await db.execute(
                select(Device).where(
                    Device.source_id == source.id,
                    Device.validation_status == "pending_review",
                )
            )
        ).scalars().all()

        rows = []
        for device in devices:
            old = {
                "title": device.title,
                "status": device.status,
                "validation_status": device.validation_status,
                "close_date": device.close_date.isoformat() if device.close_date else None,
            }
            action = "admin_only_out_of_scope"
            new_status = device.status or "standby"
            new_close_date = device.close_date
            reason = "Fiche conservée côté admin, mais non publiée car hors ciblage Afrique strict ou insuffisamment actionnable."

            if device.id in EXPIRED:
                action = "admin_only_expired"
                new_status = "expired"
                new_close_date = EXPIRED[device.id]
                reason = "Échéance passée détectée dans le contenu source."
            elif device.id in FUTURE_ADMIN_ONLY:
                action = "admin_only_future_out_of_scope"
                new_status = "open"
                new_close_date = FUTURE_ADMIN_ONLY[device.id]
                reason = "Échéance future détectée, mais fiche non prioritaire pour le ciblage Afrique strict."
            elif device.id in RECURRING_ADMIN_ONLY:
                action = "admin_only_recurring_out_of_scope"
                new_status = "recurring"
                reason = "Calendrier récurrent détecté, mais fiche non prioritaire pour le ciblage Afrique strict."

            rows.append(
                {
                    "id": str(device.id),
                    "action": action,
                    "old": old,
                    "new_status": new_status,
                    "new_validation_status": "admin_only",
                    "new_close_date": new_close_date.isoformat() if new_close_date else None,
                    "reason": reason,
                }
            )

            if dry_run:
                continue

            device.status = new_status
            device.close_date = new_close_date
            device.validation_status = "admin_only"
            _append_tags(device, "source:global_south_admin_only", "quality:out_of_public_scope")
            if action == "admin_only_expired":
                _append_tags(device, "deadline:expired")
            elif action == "admin_only_future_out_of_scope":
                _append_tags(device, "deadline:detected_admin_only")
            elif action == "admin_only_recurring_out_of_scope":
                device.is_recurring = True
                _append_tags(device, "deadline:recurring_admin_only")

            analysis = dict(device.decision_analysis or {})
            analysis["public_visibility"] = "admin_only"
            analysis["manual_requalification"] = {
                "checked_at": now,
                "reason": reason,
                "action": action,
            }
            device.decision_analysis = analysis

        if dry_run:
            await db.rollback()
        else:
            await db.commit()

    return {"dry_run": dry_run, "changed": len(rows), "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalise les fiches Global South encore en attente.")
    parser.add_argument("--apply", action="store_true", help="Applique les changements en base.")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(dry_run=not args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
