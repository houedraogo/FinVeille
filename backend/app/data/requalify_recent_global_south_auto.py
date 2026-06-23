"""Requalifie prudemment les opportunites Global South recentes exploitables."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from unidecode import unidecode

from app.collector.normalizer import Normalizer
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.services.ai_readiness import compute_ai_readiness
from app.services.content_section_builder import build_content_sections, render_sections_markdown
from app.services.user_quality import compute_user_quality
from app.utils.text_utils import clean_editorial_text, derive_device_status


PUBLIC_TYPES = {"subvention", "concours", "aap", "ami", "investissement", "accompagnement"}
BLOCKED_TITLE_MARKERS = (
    "make money online",
    "paid opportunity",
    "bursary",
    "student travel",
    "pitch for october",
)
ENGLISH_TITLE_MARKERS = (
    "applications open",
    "applications are now open",
    "opens applications",
    "opens funding",
    "funding opportunity",
    "apply by",
    "apply for funding",
    "launches",
    "travel award",
    "early-career",
)


def _source_dict() -> dict[str, Any]:
    return {
        "id": "global-south-requalification",
        "name": "Global South Opportunities - Funding",
        "organism": "Global South Opportunities",
        "country": "International",
        "url": "https://www.globalsouthopportunities.com/feed/",
        "collection_mode": "rss",
        "level": 2,
        "config": {"allow_english_text": True, "assume_standby_without_close_date": True},
        "language": "fr",
    }


def _clean_tags(tags: list[str] | None) -> list[str]:
    blocked_prefixes = (
        "source:global_south_admin_only",
        "visibility:admin_only",
        "quality:english_title_admin_only",
        "quality:missing_reliable_deadline",
        "quality:generic_type_admin_only",
    )
    cleaned = [tag for tag in (tags or []) if tag not in blocked_prefixes]
    for tag in ("source:global_south_auto_requalified", "visibility:auto_published"):
        if tag not in cleaned:
            cleaned.append(tag)
    return cleaned[:24]


def _eligible_for_publication(device: Device, fields: dict[str, Any]) -> bool:
    title = clean_editorial_text(fields.get("title") or device.title or "").lower()
    title_key = unidecode(title)
    device_type = fields.get("device_type") or device.device_type
    if any(marker in title for marker in BLOCKED_TITLE_MARKERS):
        return False
    if any(marker in title_key for marker in ENGLISH_TITLE_MARKERS):
        return False
    if device_type not in PUBLIC_TYPES:
        return False
    status = fields.get("status") or device.status
    close_date = fields.get("close_date") or device.close_date
    if status == "open" and close_date and close_date >= date.today():
        return True
    if status == "recurring" and (device.is_recurring or device.recurrence_notes):
        return True
    return False


def _mark_admin_only(device: Device, now: datetime, reason: str) -> None:
    device.validation_status = "admin_only"
    device.user_quality_decision = "admin_only"
    device.user_quality_reasons = [reason]
    tags = set(device.tags or [])
    tags.discard("visibility:auto_published")
    tags.add("visibility:admin_only")
    tags.add("source:global_south_admin_only")
    tags.add(reason)
    device.tags = sorted(tags)[:24]
    device.updated_at = now


async def run(days: int = 14) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    normalizer = Normalizer(_source_dict())
    changed: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .where(
                    Device.source_url.ilike("%globalsouthopportunities.com%"),
                    Device.created_at >= now - timedelta(days=days),
                    Device.validation_status.in_(("admin_only", "auto_published")),
                )
                .order_by(Device.created_at.desc())
            )
        ).scalars().all()

        for device in devices:
            raw_text = device.source_raw or device.full_description or device.short_description or ""
            clean_text = clean_editorial_text(raw_text)
            detected_close_date = normalizer._extract_date(clean_text, "close") or device.close_date
            detected_status = "open" if detected_close_date and detected_close_date >= date.today() else derive_device_status(detected_close_date, device.status)
            fields = normalizer._build_global_south_opportunities_fields(
                device.title or "",
                raw_text,
                detected_close_date,
                device.open_date,
            )
            if not fields:
                skipped.append({"id": str(device.id), "title": device.title or "", "reason": "no_fields"})
                continue
            fields["close_date"] = detected_close_date
            fields["status"] = detected_status

            if not _eligible_for_publication(device, fields):
                if device.validation_status == "auto_published":
                    _mark_admin_only(device, now, "global_south_title_or_scope_not_public_ready")
                    changed.append(
                        {
                            "id": str(device.id),
                            "title": device.title,
                            "type": device.device_type,
                            "close_date": str(device.close_date) if device.close_date else None,
                            "action": "hidden_admin_only",
                        }
                    )
                skipped.append({"id": str(device.id), "title": device.title or "", "reason": "not_public_ready"})
                continue

            for key in (
                "title",
                "device_type",
                "short_description",
                "full_description",
                "eligibility_criteria",
                "funding_details",
                "amount_max",
                "currency",
                "country",
                "geographic_scope",
                "aid_nature",
            ):
                if key in fields and fields[key]:
                    setattr(device, key, fields[key])

            if detected_close_date:
                device.close_date = detected_close_date
                device.status = detected_status
            device.validation_status = "auto_published"
            device.user_quality_decision = "publish_with_caution"
            device.user_quality_reasons = ["auto_requalification_global_south", "source_a_verifier"]
            device.tags = _clean_tags(device.tags)
            device.updated_at = now

            payload = {column.name: getattr(device, column.name) for column in device.__table__.columns}
            payload["tags"] = device.tags
            sections = build_content_sections(payload, _source_dict())
            device.content_sections_json = sections
            device.ai_rewritten_sections_json = sections
            rendered = render_sections_markdown(sections)
            if rendered:
                device.full_description = rendered
            readiness = compute_ai_readiness(payload, _source_dict())
            device.ai_readiness_score = readiness.score
            device.ai_readiness_label = readiness.label
            device.ai_readiness_reasons = readiness.reasons
            user_quality = compute_user_quality(payload)
            device.user_quality_score = user_quality.score

            changed.append(
                {
                    "id": str(device.id),
                    "title": device.title,
                    "type": device.device_type,
                    "close_date": str(device.close_date) if device.close_date else None,
                    "amount_max": float(device.amount_max) if device.amount_max is not None else None,
                    "currency": device.currency,
                }
            )

        await db.commit()

    return {"changed": len(changed), "skipped": len(skipped), "items": changed, "skipped_sample": skipped[:10]}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
