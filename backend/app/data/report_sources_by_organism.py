import argparse
import asyncio
import json

from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


async def run(organism: str) -> dict:
    async with AsyncSessionLocal() as db:
        sources = (
            await db.execute(
                select(Source)
                .where(Source.organism.ilike(f"%{organism}%"))
                .order_by(Source.country.asc(), Source.name.asc())
            )
        ).scalars().all()

        rows = []
        for source in sources:
            base = [Device.source_id == source.id]
            total = (await db.execute(select(func.count()).select_from(Device).where(*base))).scalar_one()
            missing_dates = (
                await db.execute(select(func.count()).select_from(Device).where(*base, Device.close_date.is_(None)))
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
                        (
                            (Device.short_description.is_(None))
                            | (func.length(func.trim(func.coalesce(Device.short_description, ""))) < 120)
                        ),
                    )
                )
            ).scalar_one()
            open_count = (
                await db.execute(select(func.count()).select_from(Device).where(*base, Device.status == "open"))
            ).scalar_one()
            recurring_count = (
                await db.execute(select(func.count()).select_from(Device).where(*base, Device.status == "recurring"))
            ).scalar_one()
            standby_count = (
                await db.execute(select(func.count()).select_from(Device).where(*base, Device.status == "standby"))
            ).scalar_one()
            expired_count = (
                await db.execute(select(func.count()).select_from(Device).where(*base, Device.status == "expired"))
            ).scalar_one()
            rows.append(
                {
                    "source_name": source.name,
                    "country": source.country,
                    "total": total,
                    "missing_dates": missing_dates,
                    "pending_review": pending_review,
                    "weak_texts": weak_texts,
                    "open": open_count,
                    "recurring": recurring_count,
                    "standby": standby_count,
                    "expired": expired_count,
                }
            )

        rows.sort(key=lambda row: (-row["missing_dates"], -row["pending_review"], -row["total"], row["country"] or ""))
        return {"organism": organism, "sources": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Rapport qualité par source pour un organisme donné.")
    parser.add_argument("organism")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.organism)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
