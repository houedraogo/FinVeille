import logging

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from datetime import date, timedelta, datetime, timezone
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.device import Device
from app.models.source import Source
from app.models.alert import Alert
from app.models.billing import BillingCustomer, Plan, Subscription, UsageEvent
from app.models.collection_log import CollectionLog
from app.models.user import User as UserModel
from app.models.organization import Organization, OrganizationMember
from app.models.operations import AuditLog, DataExport, DeletionRequest, EmailEvent
from app.models.saved_search import SavedSearch
from app.models.workspace import DevicePipeline
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.schemas.organization import OrganizationResponse
from app.dependencies import require_role
from app.utils.auth_utils import hash_password
from app.services.device_service import DeviceService
from app.tasks.quality_tasks import (
    build_catalog_audit,
    build_quality_audit,
    daily_catalog_quality_control,
    daily_quality_audit,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


async def _count_scalar(db: AsyncSession, statement) -> int:
    result = await db.execute(statement)
    return int(result.scalar() or 0)


# --- Qualité des données ---

@router.get("/quality")
async def quality_report(db: AsyncSession = Depends(get_db),
                          _=Depends(require_role(["admin", "editor"]))):
    """Rapport qualité de la base."""
    today = date.today()

    r = await db.execute(select(func.count()).where(Device.completeness_score < 40))
    incomplete = r.scalar() or 0

    r = await db.execute(select(func.count()).where(Device.close_date < today, Device.status == "open"))
    expired_open = r.scalar() or 0

    r = await db.execute(select(func.count()).where(Device.validation_status == "pending_review"))
    pending = r.scalar() or 0

    r = await db.execute(select(func.count()).where(Device.confidence_score < 30))
    low_confidence = r.scalar() or 0

    r = await db.execute(select(func.avg(Device.completeness_score)))
    avg_completeness = round(float(r.scalar() or 0), 1)

    r = await db.execute(select(func.avg(Device.confidence_score)))
    avg_confidence = round(float(r.scalar() or 0), 1)

    return {
        "incomplete_devices": incomplete,
        "expired_still_open": expired_open,
        "pending_validation": pending,
        "low_confidence": low_confidence,
        "avg_completeness": avg_completeness,
        "avg_confidence": avg_confidence,
    }


@router.post("/quality/fix-expired")
async def fix_expired_devices(db: AsyncSession = Depends(get_db),
                               _=Depends(require_role(["admin"]))):
    """Passe en 'expired' les dispositifs dont la date est dépassée."""
    today = date.today()
    result = await db.execute(
        update(Device)
        .where(and_(Device.close_date < today, Device.status == "open"))
        .values(status="expired", updated_at=datetime.now(timezone.utc))
        .returning(Device.id)
    )
    updated = result.fetchall()
    await db.commit()
    return {"fixed": len(updated), "message": f"{len(updated)} dispositifs passés en 'expired'"}


@router.post("/quality/purge-thin-descriptions")
async def purge_thin_descriptions(
    dry_run: bool = Query(True),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    """Supprime les dispositifs pending_review impossibles Ã  enrichir car trop peu dÃ©crits."""
    return await DeviceService(db).purge_unenrichable_devices(
        actor_id=str(current_user.id),
        limit=limit,
        dry_run=dry_run,
    )


@router.get("/quality/audit")
async def quality_audit(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "editor"])),
):
    """Audit qualité détaillé des dispositifs et des sources récentes."""
    return await build_quality_audit(db)


@router.get("/quality/catalog-audit")
async def catalog_audit(
    sample_limit: int = Query(8, ge=1, le=25),
    source_limit: int = Query(80, ge=10, le=300),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "editor"])),
):
    """Audit global du catalogue avec recommandations source par source."""
    return await build_catalog_audit(db, sample_limit=sample_limit, source_limit=source_limit)


@router.post("/quality/audit/run")
async def run_quality_audit(_=Depends(require_role(["admin"]))):
    """Déclenche un audit qualité en arrière-plan."""
    daily_quality_audit.delay()
    return {"message": "Audit qualité déclenché en arrière-plan"}


@router.post("/quality/catalog-audit/run")
async def run_catalog_quality_control(_=Depends(require_role(["admin"]))):
    """Declenche le controle qualite catalogue source par source."""
    daily_catalog_quality_control.delay()
    return {"message": "Controle qualite catalogue declenche en arriere-plan"}


@router.get("/quality/source-report")
async def source_quality_report(
    source_limit: int = Query(150, ge=10, le=500),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "editor"])),
):
    """Rapport source par source: volume, taux publiable, dates, erreurs et qualite moyenne."""
    audit = await build_catalog_audit(db, sample_limit=5, source_limit=source_limit)
    return {
        "generated_at": audit["generated_at"],
        "totals": audit["totals"],
        "action_counts": audit["action_counts"],
        "rows": audit["source_report"]["rows"],
    }


@router.get("/pending")
async def get_pending_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "editor"])),
):
    """Dispositifs en attente de validation."""
    params = __import__("app.schemas.device", fromlist=["DeviceSearchParams"]).DeviceSearchParams(
        validation_status="pending_review", page=page, page_size=page_size
    )
    return await DeviceService(db).search(params)


# --- Gestion utilisateurs ---

@router.get("/users", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db),
                     _=Depends(require_role(["admin"]))):
    result = await db.execute(select(UserModel).order_by(UserModel.created_at.desc()))
    return result.scalars().all()


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db),
                       _=Depends(require_role(["admin"]))):
    from sqlalchemy import select as sel
    existing = await db.execute(sel(UserModel).where(UserModel.email == data.email))
    if existing.scalar_one_or_none():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    user = UserModel(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: UUID, data: UserUpdate,
                       db: AsyncSession = Depends(get_db),
                       _=Depends(require_role(["admin"]))):
    from fastapi import HTTPException
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/organizations", response_model=List[OrganizationResponse])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
):
    result = await db.execute(select(Organization).order_by(Organization.created_at.desc()))
    return result.scalars().all()


@router.get("/operations")
async def operations_cockpit(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
):
    """Vue exploitation SaaS pour le super admin."""
    org_rows = await db.execute(
        select(Organization, Subscription, Plan)
        .outerjoin(Subscription, Subscription.organization_id == Organization.id)
        .outerjoin(Plan, Plan.id == Subscription.plan_id)
        .order_by(Organization.created_at.desc())
        .limit(50)
    )

    organizations = []
    limits_reached = []
    subscribers = []
    for org, subscription, plan in org_rows.all():
        member_rows = await db.execute(
            select(UserModel, OrganizationMember)
            .join(OrganizationMember, OrganizationMember.user_id == UserModel.id)
            .where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.is_active == True,
            )
            .order_by(OrganizationMember.role, UserModel.created_at)
        )
        members = member_rows.all()
        owners = [
            {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": membership.role,
            }
            for user, membership in members
            if membership.role in {"org_owner", "org_admin"}
        ]
        billing_customer = (
            await db.execute(
                select(BillingCustomer).where(BillingCustomer.organization_id == org.id)
            )
        ).scalar_one_or_none()
        member_count = await _count_scalar(
            db,
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.is_active == True,
            ),
        )
        usage = {
            "users": member_count,
            "alerts": await _count_scalar(
                db,
                select(func.count(Alert.id)).join(
                    OrganizationMember,
                    OrganizationMember.user_id == Alert.user_id,
                ).where(OrganizationMember.organization_id == org.id)
            ),
            "saved_searches": await _count_scalar(
                db,
                select(func.count(SavedSearch.id)).join(
                    OrganizationMember,
                    OrganizationMember.user_id == SavedSearch.user_id,
                ).where(OrganizationMember.organization_id == org.id)
            ),
            "pipeline_projects": await _count_scalar(
                db,
                select(func.count(DevicePipeline.id)).join(
                    OrganizationMember,
                    OrganizationMember.user_id == DevicePipeline.user_id,
                ).where(OrganizationMember.organization_id == org.id)
            ),
        }
        plan_limits = (plan.limits if plan else {"users": 1, "alerts": 3, "saved_searches": 5, "pipeline_projects": 10}) or {}
        reached = []
        for metric, limit in plan_limits.items():
            if isinstance(limit, int) and limit >= 0 and usage.get(metric, 0) >= limit:
                reached.append({"metric": metric, "used": usage.get(metric, 0), "limit": limit})

        if reached:
            limits_reached.append({"organization_id": str(org.id), "organization_name": org.name, "items": reached})

        organizations.append({
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "status": org.status,
            "created_at": org.created_at,
            "plan": plan.name if plan else "Free",
            "plan_slug": plan.slug if plan else "free",
            "subscription_status": subscription.status if subscription else "free",
            "usage": usage,
            "limits": plan_limits,
            "limits_reached": reached,
            "owners": owners,
            "billing_email": billing_customer.billing_email if billing_customer else None,
            "stripe_customer_id": billing_customer.stripe_customer_id if billing_customer else None,
            "stripe_subscription_id": subscription.stripe_subscription_id if subscription else None,
            "current_period_end": subscription.current_period_end if subscription else None,
        })

        if subscription and plan and plan.slug != "free":
            subscribers.append({
                "organization_id": str(org.id),
                "organization_name": org.name,
                "organization_slug": org.slug,
                "plan": plan.name,
                "plan_slug": plan.slug,
                "price_monthly_eur": plan.price_monthly_eur,
                "subscription_status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "stripe_customer_id": billing_customer.stripe_customer_id if billing_customer else None,
                "stripe_subscription_id": subscription.stripe_subscription_id,
                "billing_email": billing_customer.billing_email if billing_customer else None,
                "owners": owners,
                "member_count": member_count,
                "created_at": subscription.created_at,
            })

    audit_rows = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(20))
    email_rows = await db.execute(select(EmailEvent).order_by(EmailEvent.created_at.desc()).limit(20))
    deletion_rows = await db.execute(select(DeletionRequest).order_by(DeletionRequest.created_at.desc()).limit(20))
    export_rows = await db.execute(select(DataExport).order_by(DataExport.created_at.desc()).limit(10))
    error_rows = await db.execute(
        select(CollectionLog, Source)
        .join(Source, Source.id == CollectionLog.source_id)
        .where(CollectionLog.status.in_(["failed", "partial"]))
        .order_by(CollectionLog.started_at.desc())
        .limit(20)
    )

    totals = {
        "organizations": await _count_scalar(db, select(func.count(Organization.id))),
        "users": await _count_scalar(db, select(func.count(UserModel.id))),
        "active_subscriptions": await _count_scalar(
            db,
            select(func.count(Subscription.id)).where(Subscription.status.in_(["active", "trialing", "past_due"])),
        ),
        "limits_reached": len(limits_reached),
        "pending_deletions": await _count_scalar(
            db,
            select(func.count(DeletionRequest.id)).where(DeletionRequest.status == "pending"),
        ),
        "recent_errors": await _count_scalar(
            db,
            select(func.count(CollectionLog.id)).where(CollectionLog.status.in_(["failed", "partial"])),
        ),
    }

    return {
        "totals": totals,
        "organizations": organizations,
        "subscribers": subscribers,
        "limits_reached": limits_reached,
        "audit_logs": [
            {
                "id": str(item.id),
                "action": item.action,
                "resource_type": item.resource_type,
                "resource_id": item.resource_id,
                "user_id": str(item.user_id) if item.user_id else None,
                "organization_id": str(item.organization_id) if item.organization_id else None,
                "metadata": item.metadata_json or {},
                "created_at": item.created_at,
            }
            for item in audit_rows.scalars().all()
        ],
        "email_events": [
            {
                "id": str(item.id),
                "email": item.email,
                "template": item.template,
                "subject": item.subject,
                "status": item.status,
                "error_message": item.error_message,
                "created_at": item.created_at,
            }
            for item in email_rows.scalars().all()
        ],
        "deletion_requests": [
            {
                "id": str(item.id),
                "user_id": str(item.user_id),
                "status": item.status,
                "reason": item.reason,
                "scheduled_for": item.scheduled_for,
                "created_at": item.created_at,
            }
            for item in deletion_rows.scalars().all()
        ],
        "data_exports": [
            {
                "id": str(item.id),
                "user_id": str(item.user_id),
                "status": item.status,
                "export_type": item.export_type,
                "expires_at": item.expires_at,
                "created_at": item.created_at,
            }
            for item in export_rows.scalars().all()
        ],
        "recent_errors": [
            {
                "id": str(log.id),
                "source_id": str(source.id),
                "source_name": source.name,
                "status": log.status,
                "error_message": log.error_message,
                "started_at": log.started_at,
                "items_error": log.items_error,
            }
            for log, source in error_rows.all()
        ],
    }


@router.get("/operations/organizations/{organization_id}")
async def organization_operations_detail(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
):
    """DÃ©tail exploitation d'une organisation client."""
    result = await db.execute(
        select(Organization, Subscription, Plan)
        .outerjoin(Subscription, Subscription.organization_id == Organization.id)
        .outerjoin(Plan, Plan.id == Subscription.plan_id)
        .where(Organization.id == organization_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Organisation introuvable")

    org, subscription, plan = row
    billing_customer = (
        await db.execute(select(BillingCustomer).where(BillingCustomer.organization_id == org.id))
    ).scalar_one_or_none()

    members_result = await db.execute(
        select(UserModel, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.user_id == UserModel.id)
        .where(OrganizationMember.organization_id == org.id)
        .order_by(OrganizationMember.role, UserModel.created_at)
    )
    members = [
        {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": membership.role,
            "platform_role": user.platform_role,
            "is_active": membership.is_active,
            "joined_at": membership.joined_at,
        }
        for user, membership in members_result.all()
    ]

    member_ids = [UUID(member["id"]) for member in members]
    usage = {
        "users": len([member for member in members if member["is_active"]]),
        "alerts": 0,
        "saved_searches": 0,
        "pipeline_projects": 0,
    }
    if member_ids:
        usage["alerts"] = await _count_scalar(db, select(func.count(Alert.id)).where(Alert.user_id.in_(member_ids)))
        usage["saved_searches"] = await _count_scalar(db, select(func.count(SavedSearch.id)).where(SavedSearch.user_id.in_(member_ids)))
        usage["pipeline_projects"] = await _count_scalar(db, select(func.count(DevicePipeline.id)).where(DevicePipeline.user_id.in_(member_ids)))

    alerts_result = await db.execute(
        select(Alert, UserModel)
        .join(UserModel, UserModel.id == Alert.user_id)
        .where(Alert.user_id.in_(member_ids) if member_ids else False)
        .order_by(Alert.created_at.desc())
        .limit(20)
    )
    usage_result = await db.execute(
        select(UsageEvent)
        .where(UsageEvent.organization_id == org.id)
        .order_by(UsageEvent.created_at.desc())
        .limit(30)
    )
    audit_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == org.id)
        .order_by(AuditLog.created_at.desc())
        .limit(30)
    )

    return {
        "organization": {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "status": org.status,
            "created_at": org.created_at,
            "updated_at": org.updated_at,
            "plan": plan.name if plan else "Free",
            "plan_slug": plan.slug if plan else "free",
            "subscription_status": subscription.status if subscription else "free",
            "stripe_customer_id": billing_customer.stripe_customer_id if billing_customer else None,
            "stripe_subscription_id": subscription.stripe_subscription_id if subscription else None,
            "billing_email": billing_customer.billing_email if billing_customer else None,
            "current_period_end": subscription.current_period_end if subscription else None,
            "limits": (plan.limits if plan else {"users": 1, "alerts": 3, "saved_searches": 5, "pipeline_projects": 10}) or {},
            "usage": usage,
        },
        "members": members,
        "alerts": [
            {
                "id": str(alert.id),
                "name": alert.name,
                "frequency": alert.frequency,
                "is_active": alert.is_active,
                "criteria": alert.criteria or {},
                "owner_email": user.email,
                "created_at": alert.created_at,
                "last_triggered_at": alert.last_triggered_at,
            }
            for alert, user in alerts_result.all()
        ],
        "usage_events": [
            {
                "id": str(item.id),
                "event_type": item.event_type,
                "quantity": item.quantity,
                "metadata": item.event_metadata or {},
                "created_at": item.created_at,
            }
            for item in usage_result.scalars().all()
        ],
        "audit_logs": [
            {
                "id": str(item.id),
                "action": item.action,
                "resource_type": item.resource_type,
                "resource_id": item.resource_id,
                "metadata": item.metadata_json or {},
                "created_at": item.created_at,
            }
            for item in audit_result.scalars().all()
        ],
    }

# --- Collecte ---

@router.post("/collect/all")
async def collect_all_sources(_=Depends(require_role(["admin"]))):
    """Déclenche la collecte de toutes les sources actives."""
    try:
        from app.tasks.collect_tasks import collect_all_active
        collect_all_active.delay()
        return {"message": "Collecte globale déclenchée"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enrich")
async def enrich_devices(
    batch_size: int = Query(50, ge=1, le=200),
    _=Depends(require_role(["admin"])),
):
    """Déclenche l'enrichissement des fiches incomplètes (scraping source_url)."""
    try:
        from app.tasks.quality_tasks import enrich_missing_fields
        enrich_missing_fields.delay(batch_size=batch_size)
        return {"message": f"Enrichissement de {batch_size} fiches déclenché en arrière-plan"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rewrite")
async def bulk_rewrite_devices(
    batch_size: int = Query(20, ge=1, le=100),
    status_filter: str = Query("pending", description="Reformuler les fiches avec ce statut : pending | failed | needs_review | all"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
):
    """
    Reformule en masse les fiches IA (ai_rewritten_sections_json).
    Ne traite que les fiches qui ont des sections source (content_sections_json non vide).
    """
    from app.services.ai_rewriter import AIRewriter, REWRITE_DONE, REWRITE_NEEDS_REVIEW

    rewriter = AIRewriter()
    if not rewriter.can_rewrite():
        raise HTTPException(
            status_code=422,
            detail="Le service de reformulation IA n'est pas configuré (clé API manquante)."
        )

    # Build query to select devices that need rewriting
    query = select(Device).where(Device.validation_status == "validated")
    if status_filter != "all":
        allowed = [s.strip() for s in status_filter.split(",") if s.strip()]
        query = query.where(Device.ai_rewrite_status.in_(allowed))

    query = query.order_by(Device.updated_at.asc()).limit(batch_size)
    result = await db.execute(query)
    devices = list(result.scalars().all())

    processed = 0
    succeeded = 0
    failed = 0
    skipped = 0
    errors: list[str] = []

    for device in devices:
        # Skip devices without source sections
        if not device.content_sections_json:
            skipped += 1
            continue

        device_dict = {
            "id": str(device.id),
            "title": device.title or "",
            "organism": device.organism or "",
            "country": device.country or "",
            "device_type": device.device_type or "",
            "status": device.status or "",
            "close_date": str(device.close_date or ""),
            "amount_min": device.amount_min,
            "amount_max": device.amount_max,
            "currency": device.currency or "",
            "content_sections_json": device.content_sections_json or [],
        }

        try:
            rewrite_result = await rewriter.rewrite_device(device_dict)
            device.ai_rewritten_sections_json = rewrite_result.sections
            device.ai_rewrite_status = rewrite_result.status
            device.ai_rewrite_model = rewrite_result.model
            device.ai_rewrite_checked_at = rewrite_result.checked_at
            processed += 1
            if rewrite_result.status in (REWRITE_DONE, REWRITE_NEEDS_REVIEW):
                succeeded += 1
            else:
                failed += 1
                errors.append(f"{device.title[:40]}: {','.join(rewrite_result.issues[:2])}")
        except Exception as exc:
            failed += 1
            errors.append(f"{device.title[:40]}: {type(exc).__name__}")

    await db.commit()

    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "errors": errors[:10],
        "message": f"{succeeded}/{processed} fiches reformulées avec succès ({skipped} ignorées faute de sections source)",
    }


# --- Déduplication ---

@router.get("/dedup")
async def get_duplicates(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "editor"])),
):
    """Détecte les groupes de doublons dans la base."""
    from app.services.dedup_service import DedupService
    return await DedupService(db).find_duplicate_groups()


class MergeGroupRequest(BaseModel):
    canonical_id: str
    duplicate_ids: List[str]


@router.post("/dedup/merge")
async def merge_duplicates_auto(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
):
    """Fusionne automatiquement tous les doublons détectés."""
    from app.services.dedup_service import DedupService
    return await DedupService(db).merge_duplicates_auto()


@router.post("/dedup/merge-group")
async def merge_group(
    body: MergeGroupRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
):
    """Fusionne manuellement un groupe de doublons."""
    from app.services.dedup_service import DedupService
    try:
        return await DedupService(db).merge_group(body.canonical_id, body.duplicate_ids)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Email ---

@router.get("/email/status")
async def email_status(_=Depends(require_role(["admin"]))):
    """Vérifie la configuration et la joignabilité du serveur SMTP."""
    from app.services.notification_service import NotificationService
    return NotificationService.smtp_status()


@router.post("/email/test")
async def send_test_email(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    """Envoie un email de test à l'administrateur connecté."""
    from app.services.notification_service import NotificationService
    from fastapi import HTTPException

    status = NotificationService.smtp_status()
    if not status["reachable"]:
        raise HTTPException(
            status_code=503,
            detail=f"SMTP non joignable : {status['message']}"
        )

    html = NotificationService.build_alert_email(
        user_name=current_user.full_name or current_user.email,
        devices=[],
        alert_name="Test de configuration",
    )
    # Remplacer le corps vide par un message de test
    html = html.replace(
        "0 dispositif(s) correspondent à votre veille <strong>Test de configuration</strong>",
        "Ceci est un email de test. Si vous le recevez, votre configuration SMTP fonctionne correctement.",
    )

    ok = NotificationService.send_email(
        to=current_user.email,
        subject="[Kafundo] Test de configuration email",
        html_body=html,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Échec de l'envoi. Vérifiez les logs du backend.")

    return {"sent": True, "to": current_user.email, "message": f"Email de test envoyé à {current_user.email}"}


@router.post("/email/digest")
async def send_weekly_digest(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    """
    Envoie le digest hebdomadaire à tous les utilisateurs actifs.
    Contient : nouvelles opportunités des 7 derniers jours + deadlines J-7 de leur pipeline.
    """
    from app.services.notification_service import NotificationService
    from app.models.user import User as UserModel
    from app.models.workspace import DevicePipeline, FavoriteDevice
    from datetime import timedelta, timezone

    smtp_status = NotificationService.smtp_status()
    if not smtp_status["reachable"]:
        raise HTTPException(status_code=503, detail=f"SMTP non joignable : {smtp_status['message']}")

    # Nouvelles opportunités (7 derniers jours, validées)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    new_result = await db.execute(
        select(Device)
        .where(
            Device.validation_status.in_(["validated", "auto_published", "approved"]),
            Device.first_seen_at >= seven_days_ago,
            Device.status == "open",
        )
        .order_by(Device.first_seen_at.desc())
        .limit(20)
    )
    new_devices = list(new_result.scalars().all())

    # Opportunités qui clôturent dans 7 jours
    today = date.today()
    seven_days_ahead = today + timedelta(days=7)
    closing_result = await db.execute(
        select(Device)
        .where(
            Device.close_date >= today,
            Device.close_date <= seven_days_ahead,
            Device.status == "open",
        )
        .order_by(Device.close_date.asc())
        .limit(10)
    )
    closing_devices = list(closing_result.scalars().all())

    # Envoyer à tous les utilisateurs actifs (non-admin)
    users_result = await db.execute(
        select(UserModel).where(UserModel.is_active == True).limit(500)
    )
    users = list(users_result.scalars().all())

    sent = 0
    failed = 0
    for user in users:
        # Nombre d'items dans le pipeline de cet utilisateur
        pipeline_count_result = await db.execute(
            select(func.count(DevicePipeline.id)).where(DevicePipeline.user_id == user.id)
        )
        pipeline_count = pipeline_count_result.scalar() or 0

        html = NotificationService.build_digest_email(
            user_name=user.full_name or user.email,
            new_devices=new_devices,
            closing_devices=closing_devices,
            pipeline_count=pipeline_count,
        )
        ok = NotificationService.send_email(
            to=user.email,
            subject=f"[Kafundo] Digest hebdo — {len(new_devices)} nouvelles opportunités",
            html_body=html,
        )
        db.add(
            EmailEvent(
                user_id=user.id,
                email=user.email,
                template="new_opportunity_alert",
                subject=f"[Kafundo] {len(devices)} nouvelle(s) opportunite(s) - {alert.name}",
                status="sent" if ok else "failed",
                metadata_json={
                    "alert_id": str(alert.id),
                    "alert_name": alert.name,
                    "matches": len(devices),
                    "hours_back": hours_back,
                    "effective_since": effective_since_dt.isoformat(),
                },
            )
        )
        if ok:
            sent += 1
        else:
            failed += 1

    return {
        "sent": sent,
        "failed": failed,
        "users_targeted": len(users),
        "new_devices_included": len(new_devices),
        "closing_soon_included": len(closing_devices),
        "message": f"Digest envoyé à {sent}/{len(users)} utilisateurs",
    }


@router.post("/email/deadline-reminders")
async def send_deadline_reminders(
    days_ahead: int = Query(7, ge=1, le=30, description="Alerter sur les clôtures dans N jours"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    """
    Envoie des rappels de deadline aux utilisateurs dont des opportunités
    suivies (pipeline en cours) ferment dans N jours.
    """
    from app.services.notification_service import NotificationService
    from app.models.user import User as UserModel
    from app.models.workspace import DevicePipeline

    smtp_status = NotificationService.smtp_status()
    if not smtp_status["reachable"]:
        raise HTTPException(status_code=503, detail=f"SMTP non joignable : {smtp_status['message']}")

    today = date.today()
    deadline_limit = today + timedelta(days=days_ahead)

    # Trouver les pipelines en cours avec deadline proche
    pipeline_result = await db.execute(
        select(DevicePipeline, Device, UserModel)
        .join(Device, Device.id == DevicePipeline.device_id)
        .join(UserModel, UserModel.id == DevicePipeline.user_id)
        .where(
            DevicePipeline.pipeline_status.in_(["interessant", "candidature_en_cours", "a_etudier"]),
            Device.close_date >= today,
            Device.close_date <= deadline_limit,
            Device.status == "open",
            UserModel.is_active == True,
        )
        .order_by(UserModel.id, Device.close_date.asc())
    )
    rows = pipeline_result.all()

    # Regrouper par utilisateur
    from collections import defaultdict
    user_devices: dict = defaultdict(list)
    user_map: dict = {}
    for pipeline, device, user in rows:
        user_devices[user.id].append(device)
        user_map[user.id] = user

    sent = 0
    failed = 0
    for user_id, devices in user_devices.items():
        user = user_map[user_id]
        html = NotificationService.build_deadline_reminder_email(
            user_name=user.full_name or user.email,
            deadline_devices=devices,
        )
        ok = NotificationService.send_email(
            to=user.email,
            subject=f"[Kafundo] ⏰ {len(devices)} deadline(s) dans {days_ahead} jours",
            html_body=html,
        )
        if ok:
            sent += 1
        else:
            failed += 1

    return {
        "sent": sent,
        "failed": failed,
        "users_targeted": len(user_devices),
        "reminders_sent": sum(len(v) for v in user_devices.values()),
        "message": f"Rappels envoyés à {sent} utilisateur(s) pour {sum(len(v) for v in user_devices.values())} deadline(s)",
    }


@router.post("/email/new-opportunity-alerts")
async def send_new_opportunity_alerts(
    hours_back: int = Query(24, ge=1, le=168, description="Fenêtre de détection : N dernières heures"),
    dry_run: bool = Query(False, description="Si True, simule sans envoyer d'emails"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    """
    Pour chaque alerte active configurée pour détecter les nouvelles opportunités
    (alert_types contient 'new', channels contient 'email'), vérifie si de nouveaux
    dispositifs ajoutés dans les `hours_back` dernières heures correspondent aux
    critères. Envoie un email à l'utilisateur si des matches sont trouvés.
    Met à jour `last_triggered_at` sur l'alerte.
    """
    from app.services.notification_service import NotificationService
    from app.services.alert_service import AlertService
    from app.models.user import User as UserModel
    from datetime import timedelta, timezone

    smtp_status = NotificationService.smtp_status()
    if not smtp_status["reachable"] and not dry_run:
        raise HTTPException(status_code=503, detail=f"SMTP non joignable : {smtp_status['message']}")

    since_dt = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    alert_service = AlertService(db)
    active_alerts = await alert_service.get_all_active_new_opportunity()

    if not active_alerts:
        return {
            "sent": 0,
            "failed": 0,
            "alerts_checked": 0,
            "alerts_with_matches": 0,
            "total_matches": 0,
            "dry_run": dry_run,
            "since": since_dt.isoformat(),
            "message": "Aucune alerte active configurée pour les nouvelles opportunités.",
        }

    # Pré-charger les utilisateurs pour éviter des requêtes N+1
    user_ids = list({a.user_id for a in active_alerts})
    users_result = await db.execute(
        select(UserModel).where(UserModel.id.in_(user_ids), UserModel.is_active == True)
    )
    users_by_id = {u.id: u for u in users_result.scalars().all()}

    sent = 0
    failed = 0
    alerts_with_matches = 0
    total_matches = 0
    preview: list[dict] = []

    for alert in active_alerts:
        user = users_by_id.get(alert.user_id)
        if not user:
            continue

        effective_since_dt = alert_service.resolve_new_opportunity_since(alert, since_dt)

        try:
            devices = await alert_service.match_new_devices(alert, since_dt)
        except Exception as e:
            logger.error(f"[Alerte nouvelles oppos] Erreur matching alerte {alert.id}: {e}")
            continue

        if not devices:
            continue

        alerts_with_matches += 1
        total_matches += len(devices)
        preview.append({
            "alert_id": str(alert.id),
            "alert_name": alert.name,
            "user_email": user.email,
            "matches": len(devices),
            "effective_since": effective_since_dt.isoformat(),
        })

        if dry_run:
            continue

        html = NotificationService.build_new_opportunity_alert_email(
            user_name=user.full_name or user.email,
            alert_name=alert.name,
            devices=devices,
            total_matched=len(devices),
        )
        ok = NotificationService.send_email(
            to=user.email,
            subject=f"[Kafundo] 🔔 {len(devices)} nouvelle(s) opportunité(s) — {alert.name}",
            html_body=html,
        )
        if ok:
            sent += 1
            # Mettre à jour last_triggered_at
            alert.last_triggered_at = datetime.now(timezone.utc)
            logger.info(f"[Alerte nouvelles oppos] '{alert.name}' → {len(devices)} match(s) → {user.email}")
        else:
            failed += 1

    if not dry_run and (sent + failed) > 0:
        await db.commit()

    return {
        "sent": sent,
        "failed": failed,
        "alerts_checked": len(active_alerts),
        "alerts_with_matches": alerts_with_matches,
        "total_matches": total_matches,
        "dry_run": dry_run,
        "since": since_dt.isoformat(),
        "hours_back": hours_back,
        "preview": preview if dry_run else [],
        "message": (
            f"[DRY RUN] {alerts_with_matches} alerte(s) auraient déclenché {total_matches} notification(s)"
            if dry_run
            else f"Alertes envoyées : {sent} email(s) pour {total_matches} nouvelle(s) opportunité(s)"
        ),
    }
