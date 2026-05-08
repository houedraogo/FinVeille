from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import clean_editorial_text


SOURCE_NAME = "data.aides-entreprises.fr - aides aux entreprises"
LOCAL_MODEL = "local-editorial-fallback-v1"


SECTION_TITLES = {
    "presentation": "Présentation",
    "eligibility": "Critères d'éligibilité",
    "funding": "Montant / avantages",
    "calendar": "Calendrier",
    "procedure": "Démarche",
    "source": "Source officielle",
    "checks": "Points à vérifier",
}


def _clip(text: str | None, limit: int) -> str:
    value = clean_editorial_text(text or "")
    if len(value) <= limit:
        return value

    clipped = value[:limit].rstrip()
    sentence_end = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
    if sentence_end >= int(limit * 0.55):
        clipped = clipped[: sentence_end + 1]
    else:
        clipped = clipped.rstrip(" ,;:") + "."
    return clipped


def _section(key: str, content: str | None, *, confidence: int = 80, limit: int = 1200) -> dict[str, Any] | None:
    value = _clip(content, limit)
    if not value:
        return None
    return {
        "key": key,
        "title": SECTION_TITLES.get(key, key.replace("_", " ").title()),
        "content": value,
        "confidence": confidence,
        "source": "local_editorial_fallback",
    }


def _sections_from_existing(device: Device) -> list[dict[str, Any]]:
    raw_sections = device.ai_rewritten_sections_json or device.content_sections_json or []
    sections: list[dict[str, Any]] = []

    if isinstance(raw_sections, dict):
        iterable = [
            {"key": key, "title": SECTION_TITLES.get(key, str(key).title()), "content": value}
            for key, value in raw_sections.items()
        ]
    elif isinstance(raw_sections, list):
        iterable = raw_sections
    else:
        iterable = []

    seen: set[str] = set()
    for item in iterable:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or item.get("title") or "").strip().lower()
        if "elig" in key or "crit" in key:
            key = "eligibility"
        elif "montant" in key or "avantage" in key or "fund" in key:
            key = "funding"
        elif "calend" in key or "date" in key:
            key = "calendar"
        elif "demar" in key or "procedure" in key or "démar" in key:
            key = "procedure"
        elif "source" in key:
            key = "source"
        elif "verif" in key or "vérif" in key or "check" in key:
            key = "checks"
        else:
            key = "presentation"

        if key in seen:
            continue
        section = _section(key, item.get("content"), confidence=int(item.get("confidence") or 75))
        if section:
            sections.append(section)
            seen.add(key)

    return sections


def _calendar_text(device: Device) -> str:
    if device.close_date:
        label = device.close_date.strftime("%d/%m/%Y")
        if device.status == "expired":
            return f"La période connue s'est terminée le {label}."
        return f"La date limite actuellement identifiée est le {label}."
    if device.is_recurring or device.status == "recurring":
        return "Cette opportunité fonctionne sans fenêtre de clôture unique clairement publiée."
    return "La source officielle ne communique pas de date limite exploitable à ce stade."


def _procedure_text(device: Device) -> str:
    organism = clean_editorial_text(device.organism or "l'organisme référent")
    return f"La démarche doit être confirmée auprès de {organism} depuis la source officielle."


def _fallback_sections(device: Device) -> list[dict[str, Any]]:
    sections = [
        _section("presentation", device.short_description or device.full_description, confidence=80, limit=900),
        _section("eligibility", device.eligibility_criteria, confidence=75, limit=1300),
        _section("funding", device.funding_details, confidence=75, limit=900),
        _section("calendar", _calendar_text(device), confidence=80, limit=450),
        _section("procedure", _procedure_text(device), confidence=70, limit=450),
        _section(
            "checks",
            "Les conditions précises, les justificatifs et les modalités de dépôt doivent être confirmés sur la source officielle avant toute décision.",
            confidence=70,
            limit=450,
        ),
    ]
    return [section for section in sections if section]


def _ensure_complete_sections(device: Device) -> list[dict[str, Any]]:
    sections = _sections_from_existing(device)
    by_key = {section["key"]: section for section in sections}

    for fallback in _fallback_sections(device):
        if fallback["key"] not in by_key or len(clean_editorial_text(by_key[fallback["key"]].get("content", ""))) < 80:
            by_key[fallback["key"]] = fallback

    ordered_keys = ("presentation", "eligibility", "funding", "calendar", "procedure", "checks", "source")
    return [by_key[key] for key in ordered_keys if key in by_key]


def _build_full_description(sections: list[dict[str, Any]]) -> str:
    per_section_limits = {
        "presentation": 850,
        "eligibility": 1300,
        "funding": 900,
        "calendar": 450,
        "procedure": 550,
        "checks": 450,
        "source": 450,
    }
    blocks: list[str] = []
    for section in sections:
        key = str(section.get("key") or "")
        title = clean_editorial_text(section.get("title") or SECTION_TITLES.get(key, key.title()))
        content = _clip(section.get("content"), per_section_limits.get(key, 750))
        if title and content:
            blocks.append(f"## {title}\n{content}")
    return "\n\n".join(blocks).strip()


async def run(apply: bool = True) -> dict[str, Any]:
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
            "ai_sections_filled": 0,
            "long_full_description_shortened": 0,
            "sections_completed": 0,
        }
        preview: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for device in devices:
            before_ai = bool(device.ai_rewritten_sections_json)
            before_full_len = len(clean_editorial_text(device.full_description or ""))

            original_sections = _sections_from_existing(device)
            original_useful_sections = sum(
                1 for section in original_sections if len(clean_editorial_text(section.get("content", ""))) >= 80
            )
            needs_ai_fallback = not before_ai
            needs_shortening = before_full_len > 5800
            sections = _ensure_complete_sections(device)
            useful_sections = sum(1 for section in sections if len(clean_editorial_text(section.get("content", ""))) >= 80)
            needs_sections = original_useful_sections < 3 or useful_sections < 3

            if not (needs_ai_fallback or needs_shortening or needs_sections):
                continue

            if needs_ai_fallback or needs_sections:
                device.ai_rewritten_sections_json = sections
                device.ai_rewrite_status = "done"
                device.ai_rewrite_model = LOCAL_MODEL
                device.ai_rewrite_checked_at = now
                stats["ai_sections_filled"] += int(needs_ai_fallback)
                stats["sections_completed"] += int(needs_sections)

            if needs_shortening:
                device.full_description = _build_full_description(sections)
                stats["long_full_description_shortened"] += 1

            if len(preview) < 10:
                preview.append(
                    {
                        "title": device.title,
                        "ai_filled": needs_ai_fallback,
                        "full_len_before": before_full_len,
                        "full_len_after": len(clean_editorial_text(device.full_description or "")),
                        "sections": [section["key"] for section in sections],
                    }
                )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"source": SOURCE_NAME, "stats": stats, "preview": preview}


def main() -> None:
    import json
    import sys

    apply = "--dry-run" not in sys.argv
    print(json.dumps(asyncio.run(run(apply=apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
