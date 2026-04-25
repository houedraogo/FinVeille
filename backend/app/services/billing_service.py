from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.billing import Plan, Subscription, UsageEvent
from app.models.organization import OrganizationMember
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.models.workspace import DevicePipeline
from app.config import settings

DEFAULT_PLANS: list[dict[str, Any]] = [
    {
        "slug": "free",
        "name": "Decouverte",
        "description": "Pour découvrir Kafundo avec un accès limité aux opportunités et à la veille.",
        "price_monthly_eur": 0,
        "sort_order": 1,
        "limits": {"users": 1, "alerts": 3, "saved_searches": 5, "pipeline_projects": 15},
        "features": {
            "matching_ai": False,
            "smart_scoring": False,
            "custom_alerts": False,
            "collaboration": False,
            "advanced_analysis": False,
            "exports": False,
            "api_access": False,
            "strategic_watch": False,
            "private_sources": False,
            "funding_support": False,
        },
    },
    {
        "slug": "pro",
        "name": "Pro",
        "description": "Pour les utilisateurs individuels qui veulent détecter et prioriser les meilleures opportunités.",
        "price_monthly_eur": 49,
        "sort_order": 2,
        "limits": {"users": 1, "alerts": 25, "saved_searches": 75, "pipeline_projects": 150},
        "features": {
            "matching_ai": True,
            "smart_scoring": True,
            "custom_alerts": True,
            "collaboration": False,
            "advanced_analysis": False,
            "exports": False,
            "api_access": False,
            "strategic_watch": False,
            "private_sources": False,
            "funding_support": False,
        },
    },
    {
        "slug": "team",
        "name": "Team",
        "description": "Pour les équipes et cabinets qui veulent collaborer sur la veille et le suivi des dossiers.",
        "price_monthly_eur": 179,
        "sort_order": 3,
        "limits": {"users": 5, "alerts": 120, "saved_searches": 250, "pipeline_projects": 600},
        "features": {
            "matching_ai": True,
            "smart_scoring": True,
            "custom_alerts": True,
            "collaboration": True,
            "advanced_analysis": False,
            "exports": True,
            "api_access": False,
            "strategic_watch": False,
            "private_sources": True,
            "funding_support": False,
        },
    },
    {
        "slug": "expert",
        "name": "Expert",
        "description": "Pour les utilisateurs avancés qui ont besoin d’analyse poussée, d’exports et d’un accès API.",
        "price_monthly_eur": 399,
        "sort_order": 4,
        "limits": {"users": 10, "alerts": 250, "saved_searches": 500, "pipeline_projects": 2000},
        "features": {
            "matching_ai": True,
            "smart_scoring": True,
            "custom_alerts": True,
            "collaboration": True,
            "advanced_analysis": True,
            "exports": True,
            "api_access": True,
            "strategic_watch": True,
            "private_sources": True,
            "funding_support": False,
        },
    },
    {
        "slug": "enterprise",
        "name": "Accompagnement Financement",
        "description": "Pour les organisations qui veulent un accompagnement premium sur leur stratégie et leurs dossiers de financement.",
        "price_monthly_eur": 0,
        "sort_order": 5,
        "limits": {"users": -1, "alerts": -1, "saved_searches": -1, "pipeline_projects": -1},
        "features": {
            "matching_ai": True,
            "smart_scoring": True,
            "custom_alerts": True,
            "collaboration": True,
            "advanced_analysis": True,
            "exports": True,
            "api_access": True,
            "strategic_watch": True,
            "private_sources": True,
            "funding_support": True,
        },
    },
]


@dataclass
class BillingContext:
    organization_id: UUID | None
    plan: Plan
    subscription: Subscription | None
    usage: dict[str, int]


async def ensure_default_plans(db: AsyncSession) -> None:
    stripe_price_ids = {
        "pro": settings.STRIPE_PRICE_PRO,
        "team": settings.STRIPE_PRICE_TEAM,
        "expert": settings.STRIPE_PRICE_EXPERT,
        "enterprise": settings.STRIPE_PRICE_ENTERPRISE,
    }
    for item in DEFAULT_PLANS:
        result = await db.execute(select(Plan).where(Plan.slug == item["slug"]))
        plan = result.scalar_one_or_none()
        stripe_price_id = stripe_price_ids.get(item["slug"])
        if plan:
            plan.name = item["name"]
            plan.description = item["description"]
            plan.price_monthly_eur = item["price_monthly_eur"]
            plan.sort_order = item["sort_order"]
            plan.limits = item["limits"]
            plan.features = item["features"]
            if stripe_price_id:
                plan.stripe_price_id = stripe_price_id
            continue
        db.add(Plan(**item, stripe_price_id=stripe_price_id))
    await db.commit()


async def get_current_organization_id(db: AsyncSession, user: User) -> UUID | None:
    result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user.id, OrganizationMember.is_active == True)
        .order_by(OrganizationMember.joined_at.asc())
    )
    memberships = list(result.scalars().all())
    if not memberships:
        return None
    if user.default_organization_id:
        for membership in memberships:
            if membership.organization_id == user.default_organization_id:
                return membership.organization_id
    return memberships[0].organization_id


async def _count(db: AsyncSession, statement) -> int:
    result = await db.execute(statement)
    return int(result.scalar_one() or 0)


async def get_usage(db: AsyncSession, user: User, organization_id: UUID | None) -> dict[str, int]:
    if organization_id:
        users = await _count(
            db,
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.is_active == True,
            ),
        )
    else:
        users = 1

    return {
        "users": users,
        "alerts": await _count(db, select(func.count(Alert.id)).where(Alert.user_id == user.id)),
        "saved_searches": await _count(db, select(func.count(SavedSearch.id)).where(SavedSearch.user_id == user.id)),
        "pipeline_projects": await _count(db, select(func.count(DevicePipeline.id)).where(DevicePipeline.user_id == user.id)),
    }


async def get_billing_context(db: AsyncSession, user: User) -> BillingContext:
    organization_id = await get_current_organization_id(db, user)
    subscription = None

    if organization_id:
        sub_result = await db.execute(
            select(Subscription).where(
                Subscription.organization_id == organization_id,
                Subscription.status.in_(["active", "trialing", "past_due"]),
            )
        )
        subscription = sub_result.scalar_one_or_none()

    if subscription:
        plan_result = await db.execute(select(Plan).where(Plan.id == subscription.plan_id))
        plan = plan_result.scalar_one_or_none()
    else:
        plan_result = await db.execute(select(Plan).where(Plan.slug == "free"))
        plan = plan_result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=500, detail="Plans SaaS non initialises.")

    return BillingContext(
        organization_id=organization_id,
        plan=plan,
        subscription=subscription,
        usage=await get_usage(db, user, organization_id),
    )


def limit_allows(plan: Plan, metric: str, current: int, increment: int = 1) -> bool:
    limit = (plan.limits or {}).get(metric)
    if limit is None:
        return True
    if int(limit) < 0:
        return True
    return current + increment <= int(limit)


async def ensure_limit(db: AsyncSession, user: User, metric: str, increment: int = 1) -> BillingContext:
    context = await get_billing_context(db, user)
    if not limit_allows(context.plan, metric, context.usage.get(metric, 0), increment):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "limit_reached",
                "metric": metric,
                "plan": context.plan.slug,
                "limit": (context.plan.limits or {}).get(metric),
                "message": "Limite atteinte pour votre plan. Passez a une offre superieure pour continuer.",
            },
        )
    return context


async def ensure_feature(db: AsyncSession, user: User, feature: str) -> BillingContext:
    context = await get_billing_context(db, user)
    if not bool((context.plan.features or {}).get(feature)):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "feature_locked",
                "feature": feature,
                "plan": context.plan.slug,
                "message": "Cette fonctionnalite est disponible dans une offre superieure.",
            },
        )
    return context


async def record_usage(
    db: AsyncSession,
    user: User,
    event_type: str,
    organization_id: UUID | None = None,
    quantity: int = 1,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        UsageEvent(
            organization_id=organization_id,
            user_id=user.id,
            event_type=event_type,
            quantity=quantity,
            event_metadata=metadata or {},
        )
    )
    await db.commit()
