from typing import Optional, List
from uuid import UUID
from datetime import date, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.device import Device
from app.schemas.alert import AlertCreate, AlertUpdate


class AlertService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_alerts(self, user_id: UUID) -> List[Alert]:
        result = await self.db.execute(
            select(Alert).where(Alert.user_id == user_id).order_by(Alert.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_id(self, alert_id: UUID) -> Optional[Alert]:
        result = await self.db.execute(select(Alert).where(Alert.id == alert_id))
        return result.scalar_one_or_none()

    async def create(self, data: AlertCreate, user_id: UUID) -> Alert:
        alert = Alert(**data.model_dump(), user_id=user_id)
        self.db.add(alert)
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def update(self, alert_id: UUID, data: AlertUpdate) -> Optional[Alert]:
        alert = await self.get_by_id(alert_id)
        if not alert:
            return None
        for k, v in data.model_dump(exclude_none=True).items():
            setattr(alert, k, v)
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def delete(self, alert_id: UUID):
        alert = await self.get_by_id(alert_id)
        if alert:
            await self.db.delete(alert)
            await self.db.commit()

    async def match_devices(self, alert: Alert) -> List[Device]:
        """Retourne les dispositifs correspondant aux critères d'une alerte."""
        criteria = alert.criteria or {}
        q = select(Device).where(
            Device.validation_status.in_(["auto_published", "approved"])
        )

        if criteria.get("countries"):
            q = q.where(Device.country.in_(criteria["countries"]))
        if criteria.get("sectors"):
            q = q.where(Device.sectors.overlap(criteria["sectors"]))
        if criteria.get("device_types"):
            q = q.where(Device.device_type.in_(criteria["device_types"]))
        if criteria.get("beneficiaries"):
            q = q.where(Device.beneficiaries.overlap(criteria["beneficiaries"]))
        if criteria.get("amount_min"):
            q = q.where(Device.amount_max >= criteria["amount_min"])
        if criteria.get("close_within_days"):
            deadline = date.today() + timedelta(days=int(criteria["close_within_days"]))
            q = q.where(and_(Device.close_date <= deadline, Device.close_date >= date.today()))

        result = await self.db.execute(q.limit(100))
        return result.scalars().all()

    async def get_all_active_daily(self) -> List[Alert]:
        result = await self.db.execute(
            select(Alert).where(
                and_(Alert.is_active == True, Alert.frequency.in_(["daily", "instant"]))
            )
        )
        return result.scalars().all()
