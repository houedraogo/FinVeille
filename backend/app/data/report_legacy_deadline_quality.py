"""Audite les dates limites des anciennes fiches du catalogue."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date
from typing import Any

from sqlalchemy import and_, not_, or_, select
from unidecode import unidecode

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.data.polish_added_africa_devices import TARGET_DEVICES


MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

DATE_NUMERIC_RE = re.compile(r"\b([0-3]?\d)[/-]([01]?\d)[/-]((?:20)?\d{2})\b")
DATE_TEXT_RE = re.compile(
    r"\b([0-3]?\d)\s+("
    + "|".join(sorted((re.escape(key) for key in MONTHS), key=len, reverse=True))
    + r")\s+((?:20)?\d{2})\b",
    re.IGNORECASE,
)


def _normalize_year(year: str) -> int:
    parsed = int(year)
    if parsed < 100:
        return 2000 + parsed
    return parsed


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _date_mentions(text: str) -> set[date]:
    found: set[date] = set()
    for day, month, year in DATE_NUMERIC_RE.findall(text):
        parsed = _safe_date(_normalize_year(year), int(month), int(day))
        if parsed:
            found.add(parsed)
    for day, month, year in DATE_TEXT_RE.findall(text):
        parsed = _safe_date(_normalize_year(year), MONTHS[month.lower()], int(day))
        if parsed:
            found.add(parsed)
    return found


def _text(device: Device) -> str:
    values: list[Any] = [
        device.title,
        device.short_description,
        device.full_description,
        device.eligibility_criteria,
        device.specific_conditions,
        device.required_documents,
        device.funding_details,
        device.recurrence_notes,
        device.source_raw,
        device.content_sections_json,
        device.ai_rewritten_sections_json,
        device.decision_analysis,
    ]
    parts = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            parts.append(value)
        else:
            parts.append(json.dumps(value, ensure_ascii=False, default=str))
    return "\n".join(parts)


def _variants(close_date: date) -> set[str]:
    return {
        close_date.isoformat(),
        close_date.strftime("%d/%m/%Y"),
        close_date.strftime("%d-%m-%Y"),
        close_date.strftime("%-d/%-m/%Y") if hasattr(close_date, "strftime") else close_date.isoformat(),
    }


def _flags(device: Device, text: str, mentions: set[date], today: date) -> list[str]:
    flags: list[str] = []
    normalized = unidecode(text.lower())
    close_date = device.close_date
    tags = set(device.tags or [])

    if close_date is None:
        if device.status == "open" and not device.is_recurring:
            flags.append("open_without_close_date")
        return flags

    if device.status == "open" and close_date < today:
        flags.append("open_with_past_close_date")
    if device.status in {"recurring", "standby"} or device.is_recurring:
        flags.append("close_date_on_non_classic_deadline")
    close_date_is_supported = (
        close_date in mentions
        or "deadline:verified_from_raw" in tags
        or "deadline:known" in tags
        or "deadline:expired" in tags
    )

    if (
        "date limite non communique" in normalized or "sans date limite" in normalized
    ) and not close_date_is_supported:
        flags.append("close_date_but_text_says_unknown")

    if mentions and close_date not in mentions:
        nearby = sorted(mention for mention in mentions if abs((mention - close_date).days) <= 370)
        if nearby:
            flags.append("other_date_mentions_near_deadline")

    if not any(variant in text for variant in _variants(close_date)) and not close_date_is_supported:
        flags.append("stored_close_date_not_found_in_text")

    return flags


async def run() -> dict[str, Any]:
    recent_titles = [str(device["title"]) for device in TARGET_DEVICES]
    recent_urls = [str(device["source_url"]) for device in TARGET_DEVICES]
    today = date.today()
    flagged: list[dict[str, Any]] = []
    totals = {"scanned": 0, "with_close_date": 0, "flagged": 0}

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .where(
                    and_(
                        Device.validation_status != "rejected",
                        not_(or_(Device.title.in_(recent_titles), Device.source_url.in_(recent_urls))),
                    )
                )
                .order_by(Device.close_date.asc().nullslast(), Device.updated_at.desc().nullslast())
            )
        ).scalars().all()

        totals["scanned"] = len(devices)
        for device in devices:
            if device.close_date:
                totals["with_close_date"] += 1
            text = _text(device)
            mentions = _date_mentions(text)
            flags = _flags(device, text, mentions, today)
            if flags:
                flagged.append(
                    {
                        "id": str(device.id),
                        "title": device.title,
                        "country": device.country,
                        "source_url": device.source_url,
                        "status": device.status,
                        "validation_status": device.validation_status,
                        "close_date": str(device.close_date) if device.close_date else None,
                        "is_recurring": device.is_recurring,
                        "deadline_tags": [tag for tag in (device.tags or []) if tag.startswith("deadline:")],
                        "date_mentions": [str(item) for item in sorted(mentions)[:8]],
                        "flags": flags,
                    }
                )

    totals["flagged"] = len(flagged)
    by_flag: dict[str, int] = {}
    for item in flagged:
        for flag in item["flags"]:
            by_flag[flag] = by_flag.get(flag, 0) + 1

    return {"totals": totals, "by_flag": by_flag, "items": flagged[:200]}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
