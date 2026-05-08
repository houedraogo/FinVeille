import asyncio
import json
import sys

from sqlalchemy import func, or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


async def run(source_name: str, sample_limit: int = 25) -> dict:
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == source_name))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {source_name}")

        base = [Device.source_id == source.id]

        total = (
            await db.execute(select(func.count()).select_from(Device).where(*base))
        ).scalar_one()
        missing_dates = (
            await db.execute(
                select(func.count()).select_from(Device).where(*base, Device.close_date.is_(None))
            )
        ).scalar_one()
        pending_review = (
            await db.execute(
                select(func.count()).select_from(Device).where(*base, Device.validation_status == "pending_review")
            )
        ).scalar_one()
        weak_texts = (
            await db.execute(
                select(func.count()).select_from(Device).where(
                    *base,
                    or_(
                        Device.short_description.is_(None),
                        func.length(func.trim(func.coalesce(Device.short_description, ""))) < 120,
                    ),
                )
            )
        ).scalar_one()

        status_rows = (
            await db.execute(
                select(Device.status, func.count(Device.id))
                .where(*base)
                .group_by(Device.status)
                .order_by(func.count(Device.id).desc())
            )
        ).all()
        validation_rows = (
            await db.execute(
                select(Device.validation_status, func.count(Device.id))
                .where(*base)
                .group_by(Device.validation_status)
                .order_by(func.count(Device.id).desc())
            )
        ).all()
        missing_date_rows = (
            await db.execute(
                select(
                    Device.title,
                    Device.status,
                    Device.validation_status,
                    Device.source_url,
                )
                .where(*base, Device.close_date.is_(None))
                .order_by(Device.status, Device.title)
                .limit(sample_limit)
            )
        ).all()
        pending_review_rows = (
            await db.execute(
                select(
                    Device.title,
                    Device.status,
                    Device.close_date,
                    Device.source_url,
                    Device.validation_status,
                    Device.short_description,
                )
                .where(*base, Device.validation_status == "pending_review")
                .order_by(Device.title)
                .limit(sample_limit)
            )
        ).all()
        weak_text_rows = (
            await db.execute(
                select(
                    Device.title,
                    Device.status,
                    Device.close_date,
                    Device.source_url,
                    Device.validation_status,
                    Device.short_description,
                )
                .where(
                    *base,
                    or_(
                        Device.short_description.is_(None),
                        func.length(func.trim(func.coalesce(Device.short_description, ""))) < 120,
                    ),
                )
                .order_by(Device.title)
                .limit(sample_limit)
            )
        ).all()

        return {
            "source_name": source.name,
            "source_id": str(source.id),
            "total": total,
            "missing_dates": missing_dates,
            "pending_review": pending_review,
            "weak_texts": weak_texts,
            "statuses": [{ "status": status, "count": count } for status, count in status_rows],
            "validation_statuses": [{ "status": status, "count": count } for status, count in validation_rows],
            "missing_date_sample": [
                {
                    "title": title,
                    "status": status,
                    "validation_status": validation_status,
                    "source_url": source_url,
                }
                for title, status, validation_status, source_url in missing_date_rows
            ],
            "pending_review_sample": [
                {
                    "title": title,
                    "status": status,
                    "close_date": str(close_date) if close_date else None,
                    "source_url": source_url,
                    "validation_status": validation_status,
                    "short_description": short_description,
                }
                for title, status, close_date, source_url, validation_status, short_description in pending_review_rows
            ],
            "weak_text_sample": [
                {
                    "title": title,
                    "status": status,
                    "close_date": str(close_date) if close_date else None,
                    "source_url": source_url,
                    "validation_status": validation_status,
                    "short_description": short_description,
                }
                for title, status, close_date, source_url, validation_status, short_description in weak_text_rows
            ],
        }


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m app.data.report_source_quality <source_name>")

    source_name = " ".join(sys.argv[1:])
    result = asyncio.run(run(source_name))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
