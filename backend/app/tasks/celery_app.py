from celery import Celery
from celery.schedules import crontab

from app.config import settings


celery_app = Celery(
    "finveille",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.collect_tasks",
        "app.tasks.alert_tasks",
        "app.tasks.quality_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Paris",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,
    worker_max_tasks_per_child=50,
)

celery_app.conf.beat_schedule = {
    "collect-level1-hourly": {
        "task": "app.tasks.collect_tasks.collect_by_level",
        "schedule": crontab(minute=5),
        "args": [1],
        "options": {"queue": "collect"},
    },
    "collect-level2-6h": {
        "task": "app.tasks.collect_tasks.collect_by_level",
        "schedule": crontab(minute=30, hour="*/6"),
        "args": [2],
        "options": {"queue": "collect"},
    },
    "collect-level3-daily": {
        "task": "app.tasks.collect_tasks.collect_by_level",
        "schedule": crontab(minute=0, hour=3),
        "args": [3],
        "options": {"queue": "collect"},
    },
    "send-daily-alerts": {
        "task": "app.tasks.alert_tasks.send_daily_alerts",
        "schedule": crontab(minute=0, hour=8),
        "options": {"queue": "alerts"},
    },
    "update-expired-status": {
        "task": "app.tasks.quality_tasks.update_expired_devices",
        "schedule": crontab(minute=0, hour=1),
    },
    "enrich-missing-fields": {
        "task": "app.tasks.quality_tasks.enrich_missing_fields",
        "schedule": crontab(minute=0, hour=2),
        "kwargs": {"batch_size": 50},
    },
    "daily-quality-audit": {
        "task": "app.tasks.quality_tasks.daily_quality_audit",
        "schedule": crontab(minute=30, hour=6),
    },
    "weekly-quality-report": {
        "task": "app.tasks.quality_tasks.weekly_quality_report",
        "schedule": crontab(minute=0, hour=9, day_of_week=1),
    },
}
