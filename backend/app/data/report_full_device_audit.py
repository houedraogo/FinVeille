"""Audit complet du catalogue de fiches Kafundo."""

from __future__ import annotations

import asyncio
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from unidecode import unidecode

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.visible_quality_service import build_visible_quality_audit


PUBLIC_VALIDATION_STATUSES = {"auto_published", "approved", "validated"}
PUBLIC_USER_DECISIONS = {None, "publish", "publish_with_caution"}
ACTIONABLE_STATUSES = {"open", "recurring"}
NON_ACTIONABLE_TYPES = {"autre", "institutional_project"}
MOJIBAKE_MARKERS = ("Ã", "Â", "â€™", "â€œ", "â€", "Å")
TRUNCATED_ENDINGS = (" d'aide", " d'aid", " l'obje", " entr", " for", " vi")


def _text_blob(device: Device) -> str:
    values: list[Any] = [
        device.title,
        device.organism,
        device.country,
        device.region,
        device.zone,
        device.short_description,
        device.full_description,
        device.eligibility_criteria,
        device.eligible_expenses,
        device.specific_conditions,
        device.required_documents,
        device.funding_details,
        device.recurrence_notes,
        device.source_raw,
        device.content_sections_json,
        device.ai_rewritten_sections_json,
        device.decision_analysis,
        device.tags,
    ]
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            parts.append(value)
        else:
            parts.append(json.dumps(value, ensure_ascii=False, default=str))
    return "\n".join(parts)


def _visible(device: Device) -> bool:
    return (
        device.validation_status in PUBLIC_VALIDATION_STATUSES
        and device.user_quality_decision in PUBLIC_USER_DECISIONS
        and device.status in ACTIONABLE_STATUSES
        and device.device_type not in NON_ACTIONABLE_TYPES
    )


def _norm_key(value: str | None) -> str:
    return " ".join(unidecode(str(value or "").lower()).split())


def _item(device: Device, flags: list[str]) -> dict[str, Any]:
    return {
        "id": str(device.id),
        "title": device.title,
        "country": device.country,
        "type": device.device_type,
        "status": device.status,
        "validation_status": device.validation_status,
        "close_date": str(device.close_date) if device.close_date else None,
        "source_url": device.source_url,
        "flags": flags,
    }


def _field_quality_flags(device: Device, today: date) -> list[str]:
    flags: list[str] = []
    blob = _text_blob(device)
    short = (device.short_description or "").strip()
    full = (device.full_description or "").strip()
    eligibility = (device.eligibility_criteria or "").strip()
    funding = (device.funding_details or "").strip()
    conditions = (device.specific_conditions or "").strip()

    if any(marker in blob for marker in MOJIBAKE_MARKERS):
        flags.append("encoding_mojibake")
    if short and any(short.lower().endswith(ending) for ending in TRUNCATED_ENDINGS):
        flags.append("short_description_truncated")
    if full and any(full.lower().endswith(ending) for ending in TRUNCATED_ENDINGS):
        flags.append("full_description_truncated")
    if not device.source_url or not device.source_url.startswith(("http://", "https://")):
        flags.append("source_url_invalid")
    if device.status == "open" and device.close_date and device.close_date < today:
        flags.append("open_with_past_close_date")
    if device.status == "open" and not device.close_date and not device.is_recurring:
        flags.append("open_without_close_date")
    if device.status == "recurring" and device.close_date:
        flags.append("recurring_with_close_date")
    if _visible(device):
        if len(short) < 100:
            flags.append("visible_summary_weak")
        if len(full) < 250:
            flags.append("visible_full_description_weak")
        if len(eligibility) < 80 and not device.beneficiaries:
            flags.append("visible_eligibility_weak")
        if len(funding) < 60 and device.amount_min is None and device.amount_max is None:
            flags.append("visible_funding_weak")
        if len(conditions) < 60 and not device.required_documents:
            flags.append("visible_procedure_weak")
    return flags


async def run() -> dict[str, Any]:
    today = date.today()
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).order_by(Device.updated_at.desc().nullslast()))).scalars().all()
        sources = (await db.execute(select(Source))).scalars().all()
        visible_quality = await build_visible_quality_audit(db, limit=25)

    status_counts = Counter(device.status for device in devices)
    validation_counts = Counter(device.validation_status for device in devices)
    country_counts = Counter(device.country for device in devices)
    visible_devices = [device for device in devices if _visible(device)]

    flag_counts: Counter[str] = Counter()
    flagged_visible: list[dict[str, Any]] = []
    flagged_catalog: list[dict[str, Any]] = []
    critical_samples: dict[str, list[dict[str, Any]]] = {
        "encoding_mojibake": [],
        "open_with_past_close_date": [],
        "source_url_invalid": [],
    }
    duplicate_titles: dict[str, list[Device]] = defaultdict(list)
    duplicate_urls: dict[str, list[Device]] = defaultdict(list)

    for device in devices:
        flags = _field_quality_flags(device, today)
        flag_counts.update(flags)
        for critical_flag, rows in critical_samples.items():
            if critical_flag in flags and len(rows) < 20:
                rows.append(_item(device, flags))
        if flags:
            row = _item(device, flags)
            if _visible(device) and len(flagged_visible) < 30:
                flagged_visible.append(row)
            if len(flagged_catalog) < 30:
                flagged_catalog.append(row)
        if device.validation_status != "rejected":
            duplicate_titles[_norm_key(device.title)].append(device)
            duplicate_urls[_norm_key(device.source_url)].append(device)

    visible_title_duplicates = []
    for group in duplicate_titles.values():
        visible_group = [item for item in group if _visible(item)]
        if len(visible_group) > 1:
            visible_title_duplicates.append(
                {
                    "title": visible_group[0].title,
                    "count": len(visible_group),
                    "ids": [str(item.id) for item in visible_group[:5]],
                }
            )
    visible_title_duplicates = visible_title_duplicates[:20]

    visible_url_duplicates = []
    for group in duplicate_urls.values():
        visible_group = [item for item in group if _visible(item)]
        if len(visible_group) > 1:
            visible_url_duplicates.append(
                {
                    "source_url": visible_group[0].source_url,
                    "count": len(visible_group),
                    "titles": [item.title for item in visible_group[:5]],
                }
            )
    visible_url_duplicates = visible_url_duplicates[:20]

    sources_with_errors = [
        {
            "name": source.name,
            "country": source.country,
            "consecutive_errors": source.consecutive_errors,
            "last_success_at": source.last_success_at.isoformat() if source.last_success_at else None,
        }
        for source in sources
        if (source.consecutive_errors or 0) > 0
    ]
    sources_with_errors.sort(key=lambda item: item["consecutive_errors"] or 0, reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_date": today.isoformat(),
        "catalog": {
            "total": len(devices),
            "visible_actionable": len(visible_devices),
            "status_counts": dict(status_counts),
            "validation_counts": dict(validation_counts),
            "top_countries": dict(country_counts.most_common(20)),
        },
        "critical_findings": {
            "visible_quality_to_fix": visible_quality["to_fix_total"],
            "visible_quality_issue_counts": visible_quality["issue_counts"],
            "open_with_past_close_date": flag_counts["open_with_past_close_date"],
            "encoding_mojibake": flag_counts["encoding_mojibake"],
            "visible_title_duplicates": len(visible_title_duplicates),
            "visible_url_duplicates": len(visible_url_duplicates),
        },
        "field_quality_counts": dict(flag_counts),
        "visible_quality": {
            "visible_total": visible_quality["visible_total"],
            "to_fix_total": visible_quality["to_fix_total"],
            "action_counts": visible_quality["action_counts"],
            "items": visible_quality["items"],
        },
        "duplicates": {
            "visible_title_duplicates": visible_title_duplicates,
            "visible_url_duplicates": visible_url_duplicates,
        },
        "sources": {
            "total": len(sources),
            "with_consecutive_errors": len(sources_with_errors),
            "top_errors": sources_with_errors[:20],
        },
        "samples": {
            "critical": critical_samples,
            "flagged_visible": flagged_visible,
            "flagged_catalog": flagged_catalog,
        },
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
