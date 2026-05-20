import asyncio

from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.schemas.device import DeviceSearchParams
from app.services.device_service import DeviceService


PUBLIC_TYPES = ["subvention", "pret", "aap", "accompagnement", "garantie", "concours"]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        service = DeviceService(db)
        total = (await db.execute(select(func.count(Device.id)))).scalar_one()
        private = (
            await db.execute(
                select(func.count(Device.id)).where(Device.device_type == "investissement")
            )
        ).scalar_one()
        public = (
            await db.execute(
                select(func.count(Device.id)).where(Device.device_type.in_(PUBLIC_TYPES))
            )
        ).scalar_one()
        public_publishable = (
            await service.search(
                DeviceSearchParams(
                    device_types=PUBLIC_TYPES,
                    actionable_now=True,
                    page_size=1,
                )
            )
        )["total"]
        private_publishable = (
            await service.search(
                DeviceSearchParams(
                    device_types=["investissement"],
                    actionable_now=True,
                    page_size=1,
                )
            )
        )["total"]

    print(f"total={total}")
    print(f"private_investissement={private}")
    print(f"public_core={public}")
    print(f"public_publishable={public_publishable}")
    print(f"private_publishable={private_publishable}")


if __name__ == "__main__":
    asyncio.run(main())
