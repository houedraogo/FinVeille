from __future__ import annotations

import asyncio
import json
from collections import Counter

from sqlalchemy import Integer, cast, func, or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


AFRICA_MARKERS = (
    "afrique",
    "africa",
    "aecf",
    "awdf",
    "baobab",
    "janngo",
    "tlcom",
    "villgro",
    "orange corners",
    "tony elumelu",
    "global south",
    "vc4a",
    "i&p",
    "investisseurs & partenaires",
)


def _source_is_african(source: Source) -> bool:
    haystack = " ".join(
        [
            source.name or "",
            source.organism or "",
            source.country or "",
            source.region or "",
            source.notes or "",
            source.url or "",
        ]
    ).lower()
    return any(marker in haystack for marker in AFRICA_MARKERS)


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        sources = (await db.execute(select(Source).order_by(Source.name.asc()))).scalars().all()
        african_sources = [source for source in sources if _source_is_african(source)]
        source_ids = [source.id for source in african_sources]

        device_rows = (
            await db.execute(
                select(
                    Device.source_id,
                    func.count(Device.id),
                    func.sum(cast(Device.validation_status == "rejected", Integer)),
                    func.sum(cast(Device.close_date.is_(None), Integer)),
                    func.sum(
                        cast(
                            or_(
                                Device.short_description.is_(None),
                                func.length(func.trim(func.coalesce(Device.short_description, ""))) < 120,
                            ),
                            Integer,
                        )
                    ),
                )
                .where(Device.source_id.in_(source_ids))
                .group_by(Device.source_id)
            )
        ).all()

        metrics = {
            source_id: {
                "total": int(total or 0),
                "rejected": int(rejected or 0),
                "missing_dates": int(missing_dates or 0),
                "weak_texts": int(weak_texts or 0),
            }
            for source_id, total, rejected, missing_dates, weak_texts in device_rows
        }

        active = [source for source in african_sources if source.is_active]
        inactive = [source for source in african_sources if not source.is_active]
        empty_active = [source for source in active if metrics.get(source.id, {}).get("total", 0) == 0]
        modes = Counter(source.collection_mode for source in african_sources)
        categories = Counter(source.category for source in african_sources)

        rows = []
        for source in african_sources:
            m = metrics.get(source.id, {"total": 0, "rejected": 0, "missing_dates": 0, "weak_texts": 0})
            rows.append(
                {
                    "name": source.name,
                    "organism": source.organism,
                    "active": source.is_active,
                    "category": source.category,
                    "mode": source.collection_mode,
                    "health": max(
                        0,
                        100
                        - min(40, (source.consecutive_errors or 0) * 10)
                        - (25 if m["total"] == 0 and source.is_active else 0)
                        - min(20, m["weak_texts"] * 5),
                    ),
                    "devices": m["total"],
                    "rejected": m["rejected"],
                    "missing_dates": m["missing_dates"],
                    "weak_texts": m["weak_texts"],
                    "last_success_at": source.last_success_at.isoformat() if source.last_success_at else None,
                    "last_checked_at": source.last_checked_at.isoformat() if source.last_checked_at else None,
                    "errors": source.consecutive_errors or 0,
                    "url": source.url,
                }
            )

        rows.sort(key=lambda item: (not item["active"], item["health"], -item["devices"], item["name"]))

        return {
            "total_african_sources": len(african_sources),
            "active_sources": len(active),
            "inactive_sources": len(inactive),
            "active_without_devices": len(empty_active),
            "collection_modes": dict(modes),
            "categories": dict(categories),
            "priority_actions": [
                {
                    "source": row["name"],
                    "reason": (
                        "active_without_devices"
                        if row["active"] and row["devices"] == 0
                        else "weak_texts"
                        if row["weak_texts"]
                        else "collection_errors"
                        if row["errors"]
                        else "ok"
                    ),
                    "health": row["health"],
                    "devices": row["devices"],
                    "errors": row["errors"],
                }
                for row in rows
                if (row["active"] and row["devices"] == 0) or row["weak_texts"] or row["errors"]
            ][:15],
            "sources": rows,
        }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
