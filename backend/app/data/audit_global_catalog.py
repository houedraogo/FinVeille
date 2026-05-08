import asyncio
import json
from datetime import date

from sqlalchemy import and_, case, func, or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


WEAK_TEXT_THRESHOLD = 120


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        total = await db.scalar(select(func.count()).select_from(Device)) or 0
        missing_dates = await db.scalar(
            select(func.count()).select_from(Device).where(Device.close_date.is_(None))
        ) or 0
        pending_review = await db.scalar(
            select(func.count()).select_from(Device).where(Device.validation_status == "pending_review")
        ) or 0
        weak_texts = await db.scalar(
            select(func.count()).select_from(Device).where(
                or_(
                    Device.short_description.is_(None),
                    func.length(func.trim(func.coalesce(Device.short_description, ""))) < WEAK_TEXT_THRESHOLD,
                )
            )
        ) or 0
        no_source = await db.scalar(
            select(func.count()).select_from(Device).where(Device.source_id.is_(None))
        ) or 0
        open_with_past_close_date = await db.scalar(
            select(func.count()).select_from(Device).where(
                and_(Device.status == "open", Device.close_date.is_not(None), Device.close_date < date.today())
            )
        ) or 0

        status_rows = (
            await db.execute(
                select(Device.status, func.count(Device.id))
                .group_by(Device.status)
                .order_by(func.count(Device.id).desc())
            )
        ).all()
        validation_rows = (
            await db.execute(
                select(Device.validation_status, func.count(Device.id))
                .group_by(Device.validation_status)
                .order_by(func.count(Device.id).desc())
            )
        ).all()

        noisy_sources_rows = (
            await db.execute(
                select(
                    Source.name,
                    func.count(Device.id).label("total"),
                    func.sum(case((Device.validation_status == "pending_review", 1), else_=0)).label("pending_review"),
                    func.sum(
                        case(
                            (
                                or_(
                                    Device.short_description.is_(None),
                                    func.length(func.trim(func.coalesce(Device.short_description, ""))) < WEAK_TEXT_THRESHOLD,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("weak_texts"),
                    func.sum(case((Device.close_date.is_(None), 1), else_=0)).label("missing_dates"),
                )
                .join(Source, Device.source_id == Source.id, isouter=True)
                .group_by(Source.name)
                .having(
                    or_(
                        func.sum(case((Device.validation_status == "pending_review", 1), else_=0)) > 0,
                        func.sum(
                            case(
                                (
                                    or_(
                                        Device.short_description.is_(None),
                                        func.length(func.trim(func.coalesce(Device.short_description, ""))) < WEAK_TEXT_THRESHOLD,
                                    ),
                                    1,
                                ),
                                else_=0,
                            )
                        ) > 0,
                    )
                )
                .order_by(
                    func.sum(case((Device.validation_status == "pending_review", 1), else_=0)).desc(),
                    func.sum(
                        case(
                            (
                                or_(
                                    Device.short_description.is_(None),
                                    func.length(func.trim(func.coalesce(Device.short_description, ""))) < WEAK_TEXT_THRESHOLD,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ).desc(),
                    func.count(Device.id).desc(),
                )
            )
        ).all()

        source_status_rows = (
            await db.execute(
                select(Source.name, Device.status, func.count(Device.id))
                .join(Source, Device.source_id == Source.id)
                .where(Device.close_date.is_(None))
                .group_by(Source.name, Device.status)
                .order_by(Source.name.asc(), func.count(Device.id).desc())
            )
        ).all()

        by_source_missing: dict[str, dict[str, int]] = {}
        for source_name, status, count in source_status_rows:
            if source_name not in by_source_missing:
                by_source_missing[source_name] = {}
            by_source_missing[source_name][status or "unknown"] = int(count or 0)

        top_missing_sources = sorted(
            (
                {
                    "source_name": source_name,
                    "missing_dates": sum(status_counts.values()),
                    "statuses": status_counts,
                }
                for source_name, status_counts in by_source_missing.items()
            ),
            key=lambda item: item["missing_dates"],
            reverse=True,
        )[:15]

        return {
            "audit_date": date.today().isoformat(),
            "total": int(total),
            "missing_dates": int(missing_dates),
            "pending_review": int(pending_review),
            "weak_texts": int(weak_texts),
            "no_source": int(no_source),
            "open_with_past_close_date": int(open_with_past_close_date),
            "statuses": [{"status": status, "count": int(count)} for status, count in status_rows],
            "validation_statuses": [{"status": status, "count": int(count)} for status, count in validation_rows],
            "noisy_sources": [
                {
                    "source_name": source_name or "Sans source",
                    "total": int(total_count or 0),
                    "pending_review": int(pending_count or 0),
                    "weak_texts": int(weak_count or 0),
                    "missing_dates": int(missing_count or 0),
                }
                for source_name, total_count, pending_count, weak_count, missing_count in noisy_sources_rows
            ],
            "top_missing_date_sources": top_missing_sources,
        }


def main() -> None:
    result = asyncio.run(run())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
