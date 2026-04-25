"""
Reformule les sections metier existantes pour l'affichage public.

Usage:
    docker exec kafundo-backend python -m app.data.backfill_ai_rewrites --limit 20
    docker exec kafundo-backend python -m app.data.backfill_ai_rewrites --limit 20 --apply
    docker exec kafundo-backend python -m app.data.backfill_ai_rewrites --source-name Bpifrance --limit 50 --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.data.ensure_ai_rewrite_columns import run as ensure_ai_rewrite_columns
from app.models.device import Device
from app.models.source import Source
from app.services.ai_rewriter import AIRewriter, REWRITE_FAILED


def _device_to_dict(device: Device) -> dict[str, Any]:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


async def run(
    *,
    apply: bool = False,
    limit: int | None = 20,
    source_name: str | None = None,
    statuses: list[str] | None = None,
    include_done: bool = False,
) -> dict[str, Any]:
    await ensure_ai_rewrite_columns()
    rewriter = AIRewriter()
    statuses = statuses or ["pending", "failed", "needs_review"]

    async with AsyncSessionLocal() as db:
        query = (
            select(Device, Source)
            .outerjoin(Source, Source.id == Device.source_id)
            .where(Device.validation_status != "rejected")
            .where(Device.content_sections_json.is_not(None))
            .order_by(Device.updated_at.desc().nullslast())
        )
        if not include_done:
            query = query.where(Device.ai_rewrite_status.in_(statuses))
        if source_name:
            query = query.where(Source.name.ilike(f"%{source_name}%"))
        if limit:
            query = query.limit(limit)

        rows = (await db.execute(query)).all()
        stats: dict[str, Any] = {
            "dry_run": not apply,
            "scanned": len(rows),
            "rewritten": 0,
            "needs_review": 0,
            "failed": 0,
            "skipped_not_configured": 0,
        }
        preview: list[dict[str, Any]] = []

        for device, source in rows:
            result = await rewriter.rewrite_device(_device_to_dict(device))
            if result.status == REWRITE_FAILED and "ia_non_configuree" in result.issues:
                stats["skipped_not_configured"] += 1
                if len(preview) < 8:
                    preview.append(
                        {
                            "title": device.title,
                            "source": source.name if source else device.organism,
                            "status": result.status,
                            "issues": result.issues,
                        }
                    )
                continue

            if result.status == "done":
                stats["rewritten"] += 1
            elif result.status == "needs_review":
                stats["needs_review"] += 1
            else:
                stats["failed"] += 1

            if len(preview) < 8:
                preview.append(
                    {
                        "title": device.title,
                        "source": source.name if source else device.organism,
                        "before": (device.content_sections_json or [{}])[0].get("content", "")[:180]
                        if isinstance(device.content_sections_json, list)
                        else "",
                        "after": result.sections[0]["content"][:220] if result.sections else "",
                        "status": result.status,
                        "issues": result.issues,
                    }
                )

            if apply:
                device.ai_rewritten_sections_json = result.sections or None
                device.ai_rewrite_status = result.status
                device.ai_rewrite_model = result.model
                device.ai_rewrite_checked_at = result.checked_at

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"stats": stats, "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill des sections reformulees par IA.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--source-name", default=None)
    parser.add_argument("--status", action="append", dest="statuses", default=None)
    parser.add_argument("--include-done", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(
        run(
            apply=args.apply,
            limit=args.limit,
            source_name=args.source_name,
            statuses=args.statuses,
            include_done=args.include_done,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
