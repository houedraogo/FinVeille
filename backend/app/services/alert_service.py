from typing import Optional, List
from uuid import UUID
from datetime import date, datetime, timedelta, timezone
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
        """Calcule la borne de reprise pour eviter les doublons d'envoi."""
        last_triggered_at = alert.last_triggered_at
        if not last_triggered_at:
            return fallback_since_dt
        if last_triggered_at.tzinfo is None:
            last_triggered_at = last_triggered_at.replace(tzinfo=timezone.utc)
        return max(fallback_since_dt, last_triggered_at)

    async def match_new_devices(
        self,
        alert: Alert,
        since_dt: datetime,
    ) -> List[Device]:
        """
        Retourne les dispositifs ajoutés depuis `since_dt` qui correspondent
        aux critères de l'alerte. Filtre sur `first_seen_at >= since_dt`.
        """
        criteria = alert.criteria or {}
        effective_since_dt = self.resolve_new_opportunity_since(alert, since_dt)
        q = (
            select(Device)
            .where(
                Device.validation_status.in_(["auto_published", "approved"]),
                Device.first_seen_at >= effective_since_dt,
                Device.status.in_(["open", "recurring"]),
            )
            .order_by(Device.first_seen_at.desc())
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
        # Pas de close_within_days ici : on veut les nouvelles oppos, pas juste celles qui ferment vite

        # Filtre sur keywords (full-text titre + description) côté Python
        # pour éviter une jointure search_vector complexe
        keywords: list[str] = [k.lower() for k in (criteria.get("keywords") or [])]
        result = await self.db.execute(q.limit(200))
        devices = result.scalars().all()

        if keywords:
            devices = [
                d for d in devices
                if any(
                    kw in (d.title or "").lower()
                    or kw in (d.short_description or "").lower()
                    or kw in (d.full_description or "").lower()
                    for kw in keywords
                )
            ]

        return devices[:50]
