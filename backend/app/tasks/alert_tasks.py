import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
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
    from app.models.operations import EmailEvent
    from app.services.alert_service import AlertService
    from app.services.notification_service import NotificationService
    from datetime import datetime, timezone

    async with _fresh_db() as db:
        alert_service = AlertService(db)
        alerts = await alert_service.get_all_active_daily()

        logger.info(f"[Alertes] Traitement de {len(alerts)} alertes actives")

        for alert_id in [item.id for item in alerts]:
            try:
                alert = (await db.execute(select(Alert).where(Alert.id == alert_id)
                                          .with_for_update().execution_options(populate_existing=True))).scalar_one()
                if not alert_service.is_digest_due(alert):
                    await db.rollback()
                    continue
                devices = await alert_service.match_devices(alert)
                if not devices:
                    await db.rollback()
                    continue

                # Récupération de l'utilisateur
                r = await db.execute(select(User).where(User.id == alert.user_id))
                user = r.scalar_one_or_none()
                if not user or not user.is_active:
                    await db.rollback()
                    continue

                if "email" in (alert.channels or []) and user.email:
                    html = NotificationService.build_alert_email(
                        user_name=user.full_name or user.email,
                        devices=devices,
                        alert_name=alert.name,
                    )
                    subject = f"[Kafundo] {len(devices)} opportunite(s) - {alert.name}"
                    ok = NotificationService.send_email(
                        to=user.email,
                        subject=f"[Kafundo] {len(devices)} opportunite(s) — {alert.name}",
                        html_body=html,
                    )
                    db.add(
                        EmailEvent(
                            user_id=user.id,
                            email=user.email,
                            template="daily_alert",
                            subject=subject,
                            status="sent" if ok else "failed",
                            error_message=None if ok else "SMTP send failed",
                            metadata_json={
                                "alert_id": str(alert.id),
                                "alert_name": alert.name,
                                "matches": len(devices),
                            },
                        )
                    )
                    if ok:
                        alert.last_triggered_at = datetime.now(timezone.utc)
                        logger.info(f"[Alertes] Alerte '{alert.name}' → {len(devices)} dispositifs → {user.email}")
                await db.commit()

            except Exception as e:
                await db.rollback()
                logger.error(f"[Alertes] Erreur alerte {alert_id}: {e}")


# ─── Nouvelles opportunités ───────────────────────────────────────────────────

@celery_app.task(name="app.tasks.alert_tasks.send_new_opportunity_alerts_task", queue="alerts")
def send_new_opportunity_alerts_task(hours_back: int = 2):
    """
    Tâche Celery planifiée toutes les 2 heures.
    Vérifie si de nouvelles opportunités correspondent aux alertes actives
    (alert_types='new', channels='email') et envoie des notifications.
    """
    asyncio.run(_send_new_opportunity_alerts_async(hours_back))


async def _send_new_opportunity_alerts_async(hours_back: int = 2):
    from sqlalchemy import select
    from app.models.alert import Alert, AlertDelivery
    from app.models.user import User
    from app.models.operations import EmailEvent
    from app.services.alert_service import AlertService
    from app.services.notification_service import NotificationService

    since_dt = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    async with _fresh_db() as db:
        alert_service = AlertService(db)
        active_alerts = await alert_service.get_all_active_new_opportunity(frequencies=["instant"])

        if not active_alerts:
            logger.info("[Alerte nouvelles oppos] Aucune alerte active pour les nouvelles opportunités")
            return

        logger.info(f"[Alerte nouvelles oppos] {len(active_alerts)} alerte(s) à vérifier (depuis {since_dt.isoformat()})")

        # Pré-charger les utilisateurs
        user_ids = list({a.user_id for a in active_alerts})
        users_result = await db.execute(
            select(User).where(User.id.in_(user_ids), User.is_active == True)
        )
        users_by_id = {u.id: {"email": u.email, "full_name": u.full_name}
                       for u in users_result.scalars().all()}

        sent_count = 0
        for alert_id, user_id in [(a.id, a.user_id) for a in active_alerts]:
            user = users_by_id.get(user_id)
            if not user or not user["email"]:
                continue
            # The alert row serializes concurrent Beat/collection triggers. A
            # successful batch records each device before the next batch.
            for _ in range(5):
                try:
                    locked = (await db.execute(select(Alert).where(Alert.id == alert_id)
                                               .with_for_update().execution_options(populate_existing=True))).scalar_one()
                    devices = await alert_service.match_new_devices(locked, since_dt)
                    if not devices:
                        await db.rollback()
                        break
                    effective_since_dt = alert_service.resolve_new_opportunity_since(locked, since_dt)
                    html = NotificationService.build_new_opportunity_alert_email(
                        user_name=user["full_name"] or user["email"], alert_name=locked.name,
                        devices=devices, total_matched=len(devices),
                    )
                    ok = NotificationService.send_email(
                        to=user["email"],
                        subject=f"[Kafundo] 🔔 {len(devices)} nouvelle(s) opportunité(s) — {locked.name}",
                        html_body=html,
                    )
                    db.add(EmailEvent(
                        user_id=user_id, email=user["email"], template="new_opportunity_alert",
                        subject=f"[Kafundo] {len(devices)} nouvelle(s) opportunite(s) - {locked.name}",
                        status="sent" if ok else "failed",
                        metadata_json={"alert_id": str(locked.id), "matches": len(devices),
                                       "effective_since": effective_since_dt.isoformat()},
                    ))
                    if ok:
                        for device in devices:
                            db.add(AlertDelivery(alert_id=locked.id, device_id=device.id))
                        locked.last_triggered_at = datetime.now(timezone.utc)
                        sent_count += 1
                    await db.commit()
                    if not ok:
                        logger.warning(f"[Alerte nouvelles oppos] SMTP échoué pour {locked.id}; retry conservé")
                        break
                except Exception as e:
                    await db.rollback()
                    logger.error(f"[Alerte nouvelles oppos] Erreur alerte {alert_id}: {e}")
                    break
        logger.info(f"[Alerte nouvelles oppos] Terminé — {sent_count} email(s) envoyé(s)")
