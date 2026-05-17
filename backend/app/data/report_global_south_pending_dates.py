from __future__ import annotations

import asyncio
import json
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.data.audit_english_titles import is_africa_related
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import clean_editorial_text


DATE_PATTERNS = (
    r"\b(?:deadline|apply by|closing date|closes?|due date)[:\s-]*(.{0,80})",
    r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+20\d{2}\b",
    r"\b\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+20\d{2}\b",
    r"\b20\d{2}-\d{2}-\d{2}\b",
)


def _candidate_dates(text: str | None) -> list[str]:
    blob = clean_editorial_text(text or "").lower()
    hits: list[str] = []
    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, blob, flags=re.IGNORECASE):
            value = clean_editorial_text(match.group(0))
            if value and value not in hits:
                hits.append(value[:140])
    return hits[:6]


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(
                select(Source).where(Source.name == "Global South Opportunities - Funding")
            )
        ).scalar_one_or_none()
        if not source:
            return {"error": "source_not_found"}

        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(
                    Device.source_id == source.id,
                    Device.validation_status == "pending_review",
                )
                .order_by(Device.title.asc())
            )
        ).scalars().all()

        rows = []
        for device in devices:
            text = "\n".join(
                [
                    device.title or "",
                    device.short_description or "",
                    device.full_description or "",
                    device.funding_details or "",
                    str(device.source_raw or ""),
                ]
            )
            rows.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "country": device.country,
                    "device_type": device.device_type,
                    "status": device.status,
                    "africa_related": is_africa_related(device),
                    "date_hits": _candidate_dates(text),
                    "source_url": device.source_url,
                }
            )

        return {
            "audit_date": date.today().isoformat(),
            "count": len(rows),
            "africa_related": sum(1 for row in rows if row["africa_related"]),
            "with_date_hits": sum(1 for row in rows if row["date_hits"]),
            "rows": rows,
        }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
