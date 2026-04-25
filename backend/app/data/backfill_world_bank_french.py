import argparse
import asyncio
import json
from typing import Any

from sqlalchemy import or_, select

from app.collector.base_connector import RawItem
from app.collector.normalizer import Normalizer
from app.data.cleanup_existing_catalog import _extract_metadata_from_source_raw, _source_to_dict
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import build_structured_sections, compute_completeness, looks_english_text


WORLD_BANK_ENGLISH_MARKERS = (
    " and ",
    " oil and gas",
    "transmission and distribution",
    "public administration",
    "central government",
    "sub-national government",
    "other agriculture",
    "other water supply",
    "other industry",
    "ict services",
    "financial sector",
    "vocational education",
    "agri-business",
    "inter-urban roads",
    "program ce projet",
    "project ce projet",
    "other industrie",
    "other administration publique",
)


def _has_world_bank_english_marker(text: str | None) -> bool:
    value = (text or "").lower()
    return looks_english_text(value) or any(marker in value for marker in WORLD_BANK_ENGLISH_MARKERS)


def _needs_world_bank_localization(device: Device) -> bool:
    text = f"{device.short_description or ''}\n{device.full_description or ''}".lower()
    short = (device.short_description or "").strip().lower()
    return (
        looks_english_text(device.short_description or "")
        or looks_english_text(device.full_description or "")
        or any(marker in text for marker in WORLD_BANK_ENGLISH_MARKERS)
        or ("ce projet est porté" in short and not short.startswith("ce projet est porté"))
        or (device.device_type != "institutional_project")
    )


def _fallback_from_existing_summary(device: Device, normalizer: Normalizer) -> str | None:
    full_description = (device.full_description or "").strip()
    if "Ce projet est porté" in full_description:
        presentation = "Ce projet est porté" + full_description.split("Ce projet est porté", 1)[1]
        presentation = presentation.split("\n", 1)[0].strip(" .") + "."
        if not _has_world_bank_english_marker(presentation):
            return presentation

    text = (device.short_description or "").strip()
    if not text:
        return None

    title = (device.title or "").strip()
    if title and text.lower().startswith(title.lower()):
        text = text[len(title):].strip(" -:\n\t")
        if text.lower().startswith("ce projet"):
            return text

    country = normalizer._canonicalize_country_name(device.country)  # noqa: SLF001 - backfill cible.
    aliases = {
        "senegal": "Sénégal",
        "madagascar": "Madagascar",
        "tunisia": "Tunisie",
        "rwanda": "Rwanda",
        "morocco": "Maroc",
        "togo": "Togo",
        "kenya": "Kenya",
    }
    lowered = text.lower()
    for alias, canonical_country in aliases.items():
        if lowered.startswith(alias):
            country = country or canonical_country
            text = text[len(alias):].strip(" -:\n\t")
            break

    sectors = normalizer._localize_sector_label(text) if text else ""  # noqa: SLF001 - backfill cible.
    if country and sectors:
        return f"Ce projet est porté au {country}. Il concerne principalement les secteurs suivants : {sectors}."
    if country:
        return f"Ce projet est porté au {country}."
    return None


async def run(*, apply: bool = False, limit: int | None = None) -> dict[str, Any]:
    stats = {
        "scanned": 0,
        "localized": 0,
        "skipped": 0,
    }
    preview: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        query = (
            select(Device, Source)
            .join(Source, Source.id == Device.source_id)
            .where(
                Device.validation_status != "rejected",
                or_(
                    Device.organism.ilike("%World Bank%"),
                    Source.name.ilike("%Banque Mondiale%"),
                    Source.organism.ilike("%World Bank%"),
                    Source.url.ilike("%worldbank%"),
                ),
            )
            .order_by(Device.updated_at.desc().nullslast())
        )
        if limit:
            query = query.limit(limit)
        rows = (await db.execute(query)).all()

        for device, source in rows:
            stats["scanned"] += 1
            if not _needs_world_bank_localization(device):
                stats["skipped"] += 1
                continue

            raw_content, metadata = _extract_metadata_from_source_raw(device.source_raw)
            normalizer = Normalizer(_source_to_dict(source))
            normalized = normalizer.normalize(
                RawItem(
                    title=device.title,
                    url=device.source_url,
                    raw_content=raw_content,
                    source_id=str(device.source_id),
                    metadata=metadata,
                )
            )
            if not normalized:
                fallback = _fallback_from_existing_summary(device, normalizer)
                if not fallback:
                    stats["skipped"] += 1
                    continue
                normalized = {
                    "short_description": fallback[:500],
                    "full_description": build_structured_sections(
                        presentation=fallback,
                        funding=device.funding_details,
                        open_date=device.open_date,
                        close_date=device.close_date,
                        procedure=(
                            "La consultation detaillee se fait sur la page officielle du projet World Bank. "
                            "Les conditions et modalites doivent etre confirmees aupres de l'institution porteuse."
                        ),
                        recurrence_notes=device.recurrence_notes,
                    ),
                }

            if looks_english_text(normalized.get("short_description") or "") or looks_english_text(
                normalized.get("full_description") or ""
            ):
                summary = normalizer._compose_metadata_summary(  # noqa: SLF001 - backfill technique cible.
                    RawItem(
                        title=device.title,
                        url=device.source_url,
                        raw_content="",
                        source_id=str(device.source_id),
                        metadata=metadata,
                    ),
                    metadata,
                    normalized.get("close_date") or device.close_date,
                )
                if summary:
                    normalized["short_description"] = summary[:500]
                    normalized["full_description"] = build_structured_sections(
                        presentation=summary,
                        funding=normalized.get("funding_details"),
                        open_date=normalized.get("open_date") or device.open_date,
                        close_date=normalized.get("close_date") or device.close_date,
                        procedure=(
                            "La consultation detaillee se fait sur la page officielle du projet World Bank. "
                            "Les conditions et modalites doivent etre confirmees aupres de l'institution porteuse."
                        ),
                        recurrence_notes=normalized.get("recurrence_notes") or device.recurrence_notes,
                    )

            if _has_world_bank_english_marker(normalized.get("short_description")):
                fallback = _fallback_from_existing_summary(device, normalizer)
                if fallback and not _has_world_bank_english_marker(fallback):
                    normalized["short_description"] = fallback[:500]
                    normalized["full_description"] = build_structured_sections(
                        presentation=fallback,
                        funding=normalized.get("funding_details") or device.funding_details,
                        open_date=normalized.get("open_date") or device.open_date,
                        close_date=normalized.get("close_date") or device.close_date,
                        procedure=(
                            "La consultation detaillee se fait sur la page officielle du projet World Bank. "
                            "Les conditions et modalites doivent etre confirmees aupres de l'institution porteuse."
                        ),
                        recurrence_notes=normalized.get("recurrence_notes") or device.recurrence_notes,
                    )

            updates = {}
            for field in (
                "short_description",
                "full_description",
                "eligibility_criteria",
                "funding_details",
                "device_type",
                "country",
                "close_date",
                "open_date",
                "status",
                "is_recurring",
                "recurrence_notes",
            ):
                value = normalized.get(field)
                if value is not None and value != getattr(device, field, None):
                    updates[field] = value

            if not updates:
                stats["skipped"] += 1
                continue

            stats["localized"] += 1
            if len(preview) < 12:
                preview.append(
                    {
                        "title": device.title,
                        "before": (device.short_description or "")[:180],
                        "after": (updates.get("short_description") or device.short_description or "")[:220],
                        "fields": sorted(updates.keys()),
                    }
                )

            if apply:
                for field, value in updates.items():
                    setattr(device, field, value)
                payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
                device.completeness_score = compute_completeness(payload)

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "stats": stats, "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Francise les fiches World Bank existantes depuis source_raw.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
