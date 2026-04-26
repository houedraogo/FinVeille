from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from datetime import date, timedelta

from app.database import get_db
from app.dependencies import get_current_user
from app.models.device import Device
from app.models.relevance import OrganizationProfile
from app.models.source import Source
from app.models.collection_log import CollectionLog
from app.models.user import User
from app.services.opportunity_relevance_service import OpportunityRelevanceService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

PUBLIC_TYPES  = ["subvention", "aap", "concours", "pret", "accompagnement", "garantie"]
PRIVATE_TYPES = ["investissement"]


def _scope_conds(scope: Optional[str]) -> list:
    """Retourne les conditions SQLAlchemy de filtrage par scope (type de dispositif)."""
    if scope == "private":
        return [Device.device_type.in_(PRIVATE_TYPES)]
    if scope == "public":
        return [Device.device_type.in_(PUBLIC_TYPES)]
    return []


async def _profile_conds(db: AsyncSession, user: User) -> list:
    """Retourne les conditions de filtrage basées sur le profil de l'organisation de l'utilisateur."""
    # Les admins voient tout sans filtre de profil
    if user.role == "admin" or getattr(user, "platform_role", "member") == "super_admin":
        return []

    service = OpportunityRelevanceService(db)
    org_id = await service.get_current_organization_id(user)
    if not org_id:
        return []

    result = await db.execute(
        select(OrganizationProfile).where(OrganizationProfile.organization_id == org_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return []

    conds = []
    # Filtre par pays du profil
    if profile.countries:
        conds.append(Device.country.in_(profile.countries))

    return conds


@router.get("/")
async def get_dashboard(
    scope: Optional[str] = Query(None, regex="^(public|private|both)?$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today      = date.today()
    week_ago   = today - timedelta(days=7)
    closing_30 = today + timedelta(days=30)
    closing_7  = today + timedelta(days=7)

    # Conditions combinées : scope (type) + profil (pays)
    conds = _scope_conds(scope)
    conds += await _profile_conds(db, current_user)

    # ── Compteurs principaux ─────────────────────────────────────────────────────

    r = await db.execute(select(func.count()).where(Device.status == "open", *conds))
    total_active = r.scalar() or 0

    r = await db.execute(select(func.count()).where(*conds) if conds else select(func.count()))
    total = r.scalar() or 0

    r = await db.execute(select(func.count()).where(Device.first_seen_at >= week_ago, *conds))
    new_last_7_days = r.scalar() or 0

    # Deadlines (non pertinentes pour le scope privé)
    if scope != "private":
        r = await db.execute(
            select(func.count()).where(
                Device.close_date <= closing_30, Device.close_date >= today,
                Device.status == "open", *conds,
            )
        )
        closing_soon_30d = r.scalar() or 0

        r = await db.execute(
            select(func.count()).where(
                Device.close_date <= closing_7, Device.close_date >= today,
                Device.status == "open", *conds,
            )
        )
        closing_soon_7d = r.scalar() or 0
    else:
        closing_soon_30d = closing_soon_7d = 0

    r = await db.execute(select(func.count()).where(Device.validation_status == "pending_review", *conds))
    pending_validation = r.scalar() or 0

    # Pays distincts couverts
    r = await db.execute(
        select(func.count(Device.country.distinct())).where(*conds) if conds
        else select(func.count(Device.country.distinct()))
    )
    countries_count = r.scalar() or 0

    # Confiance moyenne
    q = select(func.avg(Device.confidence_score)).where(*conds) if conds else select(func.avg(Device.confidence_score))
    r = await db.execute(q)
    avg = r.scalar()
    avg_confidence = round(float(avg), 1) if avg else 0

    # ── Répartitions (filtrées selon le profil) ──────────────────────────────────

    q = (
        select(Device.country, func.count().label("count"))
        .group_by(Device.country)
        .order_by(func.count().desc())
        .limit(15)
    )
    if conds:
        q = q.where(*conds)
    r = await db.execute(q)
    by_country = [{"country": row[0], "count": row[1]} for row in r]

    q = (
        select(Device.device_type, func.count().label("count"))
        .group_by(Device.device_type)
        .order_by(func.count().desc())
    )
    if conds:
        q = q.where(*conds)
    r = await db.execute(q)
    by_type = [{"type": row[0], "count": row[1]} for row in r]

    q = select(Device.status, func.count().label("count")).group_by(Device.status)
    if conds:
        q = q.where(*conds)
    r = await db.execute(q)
    by_status = [{"status": row[0], "count": row[1]} for row in r]

    # ── Dispositifs récents (filtrés selon le profil) ────────────────────────────

    q = select(Device).where(Device.validation_status != "rejected")
    if conds:
        q = q.where(*conds)
    q = q.order_by(Device.first_seen_at.desc()).limit(10)
    r = await db.execute(q)
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

    # ── Clôtures imminentes (public seulement, filtrées) ─────────────────────────

    closing_soon = []
    if scope != "private":
        q = select(Device).where(
            Device.close_date <= date.today() + timedelta(days=7),
            Device.close_date >= date.today(),
            Device.status == "open",
        )
        if conds:
            q = q.where(*conds)
        q = q.order_by(Device.close_date.asc()).limit(5)
        r = await db.execute(q)
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

    # ── Santé des sources ────────────────────────────────────────────────────────

    r = await db.execute(select(func.count()).where(Source.is_active == True))
    active_sources = r.scalar() or 0

    r = await db.execute(select(func.count()).where(Source.consecutive_errors >= 3))
    sources_in_error = r.scalar() or 0

    r = await db.execute(
        select(Source)
        .where(Source.consecutive_errors >= 3)
        .order_by(Source.consecutive_errors.desc())
        .limit(6)
    )
    error_sources = [
        {"id": str(s.id), "name": s.name, "consecutive_errors": s.consecutive_errors}
        for s in r.scalars().all()
    ]

    # ── Dernière collecte ────────────────────────────────────────────────────────

    r = await db.execute(
        select(CollectionLog).order_by(CollectionLog.started_at.desc()).limit(1)
    )
    last_log = r.scalar_one_or_none()

    return {
        "total_active": total_active,
        "total": total,
        "new_last_7_days": new_last_7_days,
        "closing_soon_30d": closing_soon_30d,
        "closing_soon_7d": closing_soon_7d,
        "pending_validation": pending_validation,
        "countries_count": countries_count,
        "avg_confidence": avg_confidence,
        "by_country": by_country,
        "by_type": by_type,
        "by_status": by_status,
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
