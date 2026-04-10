from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import date, timedelta

from app.database import get_db
from app.models.device import Device
from app.models.source import Source
from app.models.collection_log import CollectionLog
from app.services.device_service import DeviceService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    device_stats = await DeviceService(db).get_stats()

    # Derniers dispositifs ajoutés
    r = await db.execute(
        select(Device)
        .where(Device.validation_status != "rejected")
        .order_by(Device.first_seen_at.desc())
        .limit(10)
    )
    recent_devices = [
        {
            "id": str(d.id),
            "title": d.title,
            "organism": d.organism,
            "country": d.country,
            "device_type": d.device_type,
            "status": d.status,
            "close_date": d.close_date.isoformat() if d.close_date else None,
            "amount_max": float(d.amount_max) if d.amount_max else None,
            "currency": d.currency,
            "confidence_score": d.confidence_score,
            "first_seen_at": d.first_seen_at.isoformat(),
        }
        for d in r.scalars().all()
    ]

    # Dispositifs à clôture imminente (7 jours)
    r = await db.execute(
        select(Device)
        .where(
            and_(
                Device.close_date <= date.today() + timedelta(days=7),
                Device.close_date >= date.today(),
                Device.status == "open",
            )
        )
        .order_by(Device.close_date.asc())
        .limit(5)
    )
    closing_soon = [
        {
            "id": str(d.id),
            "title": d.title,
            "country": d.country,
            "close_date": d.close_date.isoformat(),
            "days_left": (d.close_date - date.today()).days,
        }
        for d in r.scalars().all()
    ]

    # Santé des sources
    r = await db.execute(select(func.count()).where(Source.is_active == True))
    active_sources = r.scalar() or 0

    r = await db.execute(select(func.count()).where(Source.consecutive_errors >= 3))
    sources_in_error = r.scalar() or 0

    r = await db.execute(
        select(Source)
        .where(Source.consecutive_errors >= 3)
        .order_by(Source.consecutive_errors.desc(), Source.updated_at.desc())
        .limit(6)
    )
    error_sources = []
    for source in r.scalars().all():
        log_result = await db.execute(
            select(CollectionLog)
            .where(CollectionLog.source_id == source.id)
            .order_by(CollectionLog.started_at.desc())
            .limit(1)
        )
        last_log_for_source = log_result.scalar_one_or_none()
        error_sources.append({
            "id": str(source.id),
            "name": source.name,
            "country": source.country,
            "is_active": source.is_active,
            "consecutive_errors": source.consecutive_errors,
            "last_checked_at": source.last_checked_at.isoformat() if source.last_checked_at else None,
            "last_error": (
                (last_log_for_source.error_message or "").strip() if last_log_for_source else None
            ) or source.notes,
        })

    # Dernière collecte
    r = await db.execute(
        select(CollectionLog).order_by(CollectionLog.started_at.desc()).limit(1)
    )
    last_log = r.scalar_one_or_none()

    return {
        **device_stats,
        "recent_devices": recent_devices,
        "closing_soon": closing_soon,
        "sources": {
            "active": active_sources,
            "in_error": sources_in_error,
            "errors": error_sources,
        },
        "last_collection": {
            "at": last_log.started_at.isoformat() if last_log else None,
            "status": last_log.status if last_log else None,
            "items_new": last_log.items_new if last_log else 0,
        },
    }
