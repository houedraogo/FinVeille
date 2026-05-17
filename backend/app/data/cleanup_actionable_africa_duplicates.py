from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source


GSMA_TITLES = {
    "GSMA Innovation Fund for Green Transition for Mobile",
    "Fonds d'innovation GSMA - transition verte par le mobile",
}
GSMA_URL = (
    "https://www.gsma.com/newsroom/press-release/"
    "gsma-launches-innovation-fund-to-accelerate-green-transition-through-mobile-technology/"
)


async def run() -> dict[str, object]:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(select(Source).where(Source.name == "GSMA Innovation Fund - calls"))
        ).scalar_one_or_none()
        if source is None:
            return {"status": "skipped", "reason": "GSMA source not found"}

        devices = (
            await db.execute(
                select(Device)
                .where(Device.source_id == source.id)
                .where((Device.title.in_(GSMA_TITLES)) | (Device.source_url == GSMA_URL))
                .order_by(Device.created_at.asc())
            )
        ).scalars().all()

        if not devices:
            return {"status": "skipped", "reason": "no GSMA devices found"}

        keeper = next(
            (
                device
                for device in devices
                if device.title == "Fonds d'innovation GSMA - transition verte par le mobile"
            ),
            devices[0],
        )
        keeper.title = "Fonds d'innovation GSMA - transition verte par le mobile"
        keeper.title_normalized = keeper.title.lower()
        keeper.language = "fr"
        keeper.validation_status = "auto_published"
        keeper.last_verified_at = now

        archived: list[dict[str, str]] = []
        for device in devices:
            if device.id == keeper.id:
                continue
            device.validation_status = "admin_only"
            device.status = "expired"
            device.tags = list(dict.fromkeys([*(device.tags or []), "duplicate_archived"]))[:12]
            device.last_verified_at = now
            archived.append({"id": str(device.id), "title": device.title})

        generic_gsma = (
            await db.execute(
                select(Device).where(
                    Device.title == "Fonds d'innovation GSMA",
                    Device.status == "standby",
                )
            )
        ).scalar_one_or_none()
        if generic_gsma is not None:
            generic_gsma.validation_status = "admin_only"
            generic_gsma.tags = list(dict.fromkeys([*(generic_gsma.tags or []), "generic_signal_archived"]))[:12]
            generic_gsma.last_verified_at = now
            archived.append({"id": str(generic_gsma.id), "title": generic_gsma.title})

        await db.commit()
        return {
            "status": "ok",
            "keeper": {"id": str(keeper.id), "title": keeper.title},
            "archived_duplicates": archived,
        }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
