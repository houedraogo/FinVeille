"""
Genere les sections metier standardisees pour les fiches existantes.

Usage:
    docker exec kafundo-backend python -m app.data.backfill_content_sections
    docker exec kafundo-backend python -m app.data.backfill_content_sections --apply
"""
import argparse
import asyncio
import json
from typing import Any

from sqlalchemy import select, text

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.content_section_builder import build_content_sections, render_sections_markdown
from app.utils.text_utils import compute_completeness


def _device_to_dict(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


def _source_to_dict(source: Source | None) -> dict[str, Any] | None:
    if not source:
        return None
    return {
        "id": str(source.id),
        "name": source.name,
        "organism": source.organism,
        "url": source.url,
        "source_type": source.source_type,
        "reliability": source.reliability,
        "category": source.category,
    }


async def ensure_column() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                """
                ALTER TABLE devices
                ADD COLUMN IF NOT EXISTS content_sections_json JSON NULL
                """
            )
        )
        await db.commit()


async def run(
    *,
    apply: bool = False,
    limit: int | None = None,
    force: bool = False,
    source_name: str | None = None,
) -> dict[str, Any]:
    await ensure_column()

    async with AsyncSessionLocal() as db:
        query = (
            select(Device, Source)
            .outerjoin(Source, Source.id == Device.source_id)
            .where(Device.validation_status != "rejected")
            .order_by(Device.updated_at.desc().nullslast())
        )
        if source_name:
            query = query.where(Source.name == source_name)
        if limit:
            query = query.limit(limit)
        rows = (await db.execute(query)).all()

        stats = {
            "scanned": len(rows),
            "updated": 0,
            "sections_created": 0,
            "full_description_updated": 0,
        }
        preview = []

        for device, source in rows:
            payload = _device_to_dict(device)
            sections = build_content_sections(payload, _source_to_dict(source))
            markdown = render_sections_markdown(sections)

            current_sections = device.content_sections_json or []
            needs_sections = current_sections != sections
            needs_markdown = force or (bool(markdown) and not all(
                marker in (device.full_description or "")
                for marker in (
                    "## Presentation",
                    "## Eligibilite",
                    "## Montant / avantages",
                    "## Calendrier",
                    "## Source officielle",
                    "## Points a verifier",
                )
            ))
            if not needs_sections and not needs_markdown:
                continue

            if len(preview) < 8:
                preview.append(
                    {
                        "title": device.title,
                        "source": source.name if source else device.organism,
                        "sections": [section["key"] for section in sections],
                        "before": (device.full_description or "")[:160],
                        "after": markdown[:220],
                    }
                )

            stats["updated"] += 1
            stats["sections_created"] += len(sections)
            if needs_markdown:
                stats["full_description_updated"] += 1

            if apply:
                device.content_sections_json = sections
                if needs_markdown:
                    device.full_description = markdown
                device.completeness_score = compute_completeness(_device_to_dict(device))

        if apply:
            await db.commit()
        else:
            await db.rollback()

        stats["dry_run"] = not apply
        return {"stats": stats, "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill des sections metier structurees.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--source-name", type=str, default=None)
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(
                run(
                    apply=args.apply,
                    limit=args.limit,
                    force=args.force,
                    source_name=args.source_name,
                )
            ),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
