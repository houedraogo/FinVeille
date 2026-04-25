"""
Reclasse la taxonomie des fiches existantes sans inventer de nature metier.

Usage:
    docker exec kafundo-backend python -m app.data.backfill_taxonomy
    docker exec kafundo-backend python -m app.data.backfill_taxonomy --apply
"""
import argparse
import asyncio
import json
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.taxonomy_classifier import classify_taxonomy
from app.utils.text_utils import compute_completeness


def _source_to_dict(source: Source | None) -> dict[str, Any] | None:
    if not source:
        return None
    return {
        "name": source.name,
        "organism": source.organism,
        "url": source.url,
        "source_type": source.source_type,
        "category": source.category,
    }


def _device_to_dict(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


def _apply_taxonomy(device: Device, source: Source | None) -> list[str]:
    changed: list[str] = []
    taxonomy = classify_taxonomy(_device_to_dict(device), _source_to_dict(source))
    current_type = device.device_type or "autre"
    should_change_type = current_type in {"", "autre"} or (
        taxonomy.device_type == "institutional_project"
        and source
        and ("world bank" in (source.organism or "").lower() or "banque mondiale" in (source.name or "").lower())
    )
    target_type = taxonomy.device_type if should_change_type and taxonomy.confidence >= 55 else current_type
    taxonomy_tag = taxonomy.taxonomy_tag if target_type == taxonomy.device_type else f"taxonomy:{target_type}"

    tags = set(device.tags or [])
    old_taxonomy_tags = {tag for tag in tags if tag.startswith("taxonomy:")}
    old_taxonomy_tags.update(tag for tag in tags if tag.startswith("taxonomy_confidence:"))
    tags.difference_update(old_taxonomy_tags)
    tags.add(taxonomy_tag)
    tags.add(f"taxonomy_confidence:{taxonomy.confidence}")

    if device.device_type != target_type:
        device.device_type = target_type
        changed.append("device_type")

    if sorted(tags) != (device.tags or []):
        device.tags = sorted(tags)
        changed.append("tags")

    if changed:
        device.completeness_score = compute_completeness(_device_to_dict(device))
    return changed


async def run(*, apply: bool = False, limit: int | None = None) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        query = (
            select(Device, Source)
            .outerjoin(Source, Source.id == Device.source_id)
            .where(Device.validation_status != "rejected")
            .order_by(Device.updated_at.desc().nullslast())
        )
        if limit:
            query = query.limit(limit)
        rows = (await db.execute(query)).all()

        stats = {
            "scanned": len(rows),
            "device_type_changed": 0,
            "tagged": 0,
            "by_target_type": {},
        }
        preview = []

        with db.no_autoflush:
            for device, source in rows:
                before_type = device.device_type
                before_tags = list(device.tags or [])
                taxonomy = classify_taxonomy(_device_to_dict(device), _source_to_dict(source))

                if apply:
                    changed = _apply_taxonomy(device, source)
                    after_type = device.device_type
                    after_tags = list(device.tags or [])
                    taxonomy_tag = next((tag for tag in after_tags if tag.startswith("taxonomy:")), taxonomy.taxonomy_tag)
                else:
                    should_change_type = before_type in {"", "autre"} or (
                        taxonomy.device_type == "institutional_project"
                        and source
                        and (
                            "world bank" in (source.organism or "").lower()
                            or "banque mondiale" in (source.name or "").lower()
                        )
                    )
                    after_type = taxonomy.device_type if should_change_type and taxonomy.confidence >= 55 else before_type
                    taxonomy_tag = taxonomy.taxonomy_tag if after_type == taxonomy.device_type else f"taxonomy:{after_type}"
                    after_tags = sorted(
                        (
                            set(before_tags)
                            - {
                                tag
                                for tag in before_tags
                                if tag.startswith("taxonomy:") or tag.startswith("taxonomy_confidence:")
                            }
                        )
                        | {taxonomy_tag, f"taxonomy_confidence:{taxonomy.confidence}"}
                    )
                    changed = []
                    if after_type != before_type:
                        changed.append("device_type")
                    if after_tags != before_tags:
                        changed.append("tags")

                if not changed:
                    continue
                if "device_type" in changed:
                    stats["device_type_changed"] += 1
                    stats["by_target_type"][after_type] = stats["by_target_type"].get(after_type, 0) + 1
                if "tags" in changed:
                    stats["tagged"] += 1

                if len(preview) < 15:
                    preview.append(
                        {
                            "title": device.title,
                            "source": source.name if source else device.organism,
                            "from": {"device_type": before_type, "tags": before_tags},
                            "to": {
                            "device_type": after_type,
                            "taxonomy_tag": taxonomy_tag,
                            "confidence": taxonomy.confidence,
                            "reason": taxonomy.reason,
                        },
                            "changed": changed,
                        }
                    )

        if apply:
            await db.commit()
        else:
            await db.rollback()

        stats["dry_run"] = not apply
        return {"stats": stats, "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill de la taxonomie des dispositifs.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
