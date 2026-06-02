"""Audit des fiches visibles qui semblent cibler un pays précis mais remontent via une zone large."""

import asyncio
import json

from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.schemas.device import DeviceSearchParams
from app.services.device_service import DeviceService


TARGETS = {
    "Burkina Faso": ["burkina", "faso"],
    "Bénin": ["bénin", "benin"],
    "Côte d'Ivoire": ["côte d'ivoire", "cote d'ivoire", "ivoire"],
}


def _blob(device: Device) -> str:
    return " ".join(
        [
            device.title or "",
            device.short_description or "",
            device.full_description or "",
            device.eligibility_criteria or "",
            device.funding_details or "",
        ]
    ).lower()


async def main():
    report = {"regional_country_mentions": {}, "search_leaks": {}}
    async with AsyncSessionLocal() as db:
        for country, keywords in TARGETS.items():
            clauses = []
            for keyword in keywords:
                pattern = f"%{keyword}%"
                clauses.extend(
                    [
                        Device.title.ilike(pattern),
                        Device.short_description.ilike(pattern),
                        Device.full_description.ilike(pattern),
                    ]
                )
            rows = (
                await db.execute(
                    select(Device)
                    .where(Device.country.in_(["Afrique", "Afrique de l'Ouest"]))
                    .where(or_(*clauses))
                    .where(Device.validation_status.in_(["auto_published", "approved", "validated"]))
                    .order_by(Device.updated_at.desc())
                )
            ).scalars().all()
            report["regional_country_mentions"][country] = [
                {
                    "id": str(device.id),
                    "title": device.title,
                    "country": device.country,
                    "status": device.status,
                    "type": device.device_type,
                    "decision": device.user_quality_decision,
                }
                for device in rows
            ]

        service = DeviceService(db)
        for selected_country, keywords in TARGETS.items():
            result = await service.search(
                DeviceSearchParams(
                    countries=[selected_country],
                    actionable_now=True,
                    sort_by="relevance",
                    page=1,
                    page_size=100,
                )
            )
            leaks = []
            other_keywords = [
                (country, keys)
                for country, keys in TARGETS.items()
                if country != selected_country
            ]
            for device in result["items"]:
                text = _blob(device)
                for country, keys in other_keywords:
                    if any(key in text for key in keys):
                        leaks.append(
                            {
                                "selected_country": selected_country,
                                "mentioned_country": country,
                                "id": str(device.id),
                                "title": device.title,
                                "country": device.country,
                                "status": device.status,
                                "type": device.device_type,
                            }
                        )
                        break
            report["search_leaks"][selected_country] = {
                "total": result["total"],
                "leaks": leaks,
            }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
