import asyncio
import logging
from contextlib import asynccontextmanager
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _fresh_db():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL, pool_size=3, max_overflow=5)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


@celery_app.task(queue="alerts")
def send_daily_alerts():
    asyncio.run(_send_daily_alerts_async())


async def _send_daily_alerts_async():
    from sqlalchemy import select
    from app.models.alert import Alert
    from app.models.user import User
    from app.services.alert_service import AlertService
    from app.services.notification_service import NotificationService
    from datetime import datetime, timezone

    async with _fresh_db() as db:
        alert_service = AlertService(db)
        alerts = await alert_service.get_all_active_daily()

        logger.info(f"[Alertes] Traitement de {len(alerts)} alertes actives")

        for alert in alerts:
            try:
                devices = await alert_service.match_devices(alert)
                if not devices:
                    continue

                # Récupération de l'utilisateur
                r = await db.execute(select(User).where(User.id == alert.user_id))
                user = r.scalar_one_or_none()
                if not user or not user.is_active:
                    continue

                if "email" in (alert.channels or []) and user.email:
                    html = NotificationService.build_alert_email(
                        user_name=user.full_name or user.email,
                        devices=devices,
                        alert_name=alert.name,
                    )
                    NotificationService.send_email(
                        to=user.email,
                        subject=f"[FinVeille] {len(devices)} dispositif(s) — {alert.name}",
                        html_body=html,
                    )

                # MAJ last_triggered_at
                alert.last_triggered_at = datetime.now(timezone.utc)
                logger.info(f"[Alertes] Alerte '{alert.name}' → {len(devices)} dispositifs → {user.email}")

            except Exception as e:
                logger.error(f"[Alertes] Erreur alerte {alert.id}: {e}")

        await db.commit()
