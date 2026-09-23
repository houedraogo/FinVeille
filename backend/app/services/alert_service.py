from typing import Optional, List
from uuid import UUID
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertDelivery
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

    async def create(self, data: AlertCreate, user_id: UUID, organization_id: UUID | None = None) -> Alert:
        alert = Alert(**data.model_dump(), user_id=user_id, organization_id=organization_id)
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
        q = self._matching_query(alert)
        result = await self.db.execute(q.order_by(Device.first_seen_at.desc(), Device.id).limit(100))
        return result.scalars().all()

    @staticmethod
    def _matching_query(alert: Alert):
        criteria = alert.criteria or {}
        today = datetime.now(timezone.utc).date()
        q = select(Device).where(
            Device.validation_status.in_(["auto_published", "approved"]),
            Device.status.in_(["open", "recurring"]),
            or_(Device.close_date.is_(None), Device.close_date >= today, Device.is_recurring.is_(True)),
        )

        if criteria.get("countries"):
            q = q.where(Device.country.in_(criteria["countries"]))
        if criteria.get("sectors"):
            q = q.where(Device.sectors.overlap(criteria["sectors"]))
        if criteria.get("device_types"):
            q = q.where(Device.device_type.in_(criteria["device_types"]))
        if criteria.get("beneficiaries"):
            q = q.where(Device.beneficiaries.overlap(criteria["beneficiaries"]))
        if criteria.get("amount_min") is not None:
            q = q.where(Device.amount_max >= criteria["amount_min"])
        if criteria.get("close_within_days"):
            deadline = today + timedelta(days=int(criteria["close_within_days"]))
            q = q.where(and_(Device.close_date <= deadline, Device.close_date >= today))
        keywords = [str(k).strip() for k in criteria.get("keywords", []) if str(k).strip()]
        if keywords:
            q = q.where(or_(*[
                or_(Device.title.ilike(f"%{keyword}%"),
                    Device.short_description.ilike(f"%{keyword}%"),
                    Device.full_description.ilike(f"%{keyword}%"))
                for keyword in keywords
            ]))
        return q

    async def get_all_active_daily(self) -> List[Alert]:
        result = await self.db.execute(
            select(Alert).where(
                and_(Alert.is_active == True, Alert.frequency.in_(["daily", "weekly"]))
            )
        )
        return [alert for alert in result.scalars().all() if self.is_digest_due(alert)]

    @staticmethod
    def is_digest_due(alert: Alert) -> bool:
        if alert.frequency not in {"daily", "weekly"} or not alert.is_active:
            return False
        last = alert.last_triggered_at
        if last is None:
            return True
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - last >= timedelta(days=7 if alert.frequency == "weekly" else 1)

    async def get_all_active_new_opportunity(self, frequencies: Optional[list[str]] = None) -> List[Alert]:
        """
        Retourne les alertes actives configurées pour détecter les nouvelles
        opportunités (alert_types contient 'new', channels contient 'email').
        """
        result = await self.db.execute(
            select(Alert).where(
                Alert.is_active == True,
            )
        )
        all_alerts = result.scalars().all()
        # Filtre Python : PostgreSQL ARRAY overlap en pur Python pour éviter
        # les problèmes de dialect sur les listes vides
        return [
            a for a in all_alerts
            if "new" in (a.alert_types or [])
            and "email" in (a.channels or [])
            and (not frequencies or (a.frequency or "daily") in frequencies)
        ]

    def resolve_new_opportunity_since(
        self,
        alert: Alert,
        fallback_since_dt: datetime,
    ) -> datetime:
        """A new alert starts at creation; confirmed deliveries prevent repeats."""
        created = alert.created_at or fallback_since_dt
        return created.replace(tzinfo=timezone.utc) if created.tzinfo is None else created

    async def match_new_devices(
        self,
        alert: Alert,
        since_dt: datetime,
    ) -> List[Device]:
        """
        Retourne les dispositifs ajoutés depuis `since_dt` qui correspondent
        aux critères de l'alerte. Filtre sur `first_seen_at >= since_dt`.
        """
        effective_since_dt = self.resolve_new_opportunity_since(alert, since_dt)
        delivered = select(AlertDelivery.device_id).where(
            AlertDelivery.alert_id == alert.id, AlertDelivery.device_id == Device.id,
        ).exists()
        q = (self._matching_query(alert)
             .where(Device.first_seen_at >= effective_since_dt, ~delivered)
             .order_by(Device.first_seen_at, Device.id).limit(50))
        result = await self.db.execute(q)
        return result.scalars().all()
