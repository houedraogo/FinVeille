from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.billing import BillingCustomer, Plan, Subscription
from app.models.organization import Organization
from app.models.user import User
from app.schemas.billing import (
    BillingPortalResponse,
    CheckoutRequest,
    CheckoutResponse,
    PlanResponse,
    SubscriptionResponse,
)
from app.services.billing_service import get_billing_context, get_current_organization_id, record_usage

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def _stripe():
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY non configure.")
    try:
        import stripe
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="Le package stripe n'est pas installe.") from exc
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _dt(timestamp: int | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)


def _obj_get(obj, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _uuid(value: str | None):
    return UUID(str(value)) if value else None


async def _get_plan_by_price(db: AsyncSession, price_id: str | None) -> Plan | None:
    if not price_id:
        return None
    result = await db.execute(select(Plan).where(Plan.stripe_price_id == price_id))
    return result.scalar_one_or_none()


async def _get_or_create_customer(
    db: AsyncSession,
    stripe,
    organization_id,
    current_user: User,
) -> BillingCustomer:
    result = await db.execute(select(BillingCustomer).where(BillingCustomer.organization_id == organization_id))
    customer = result.scalar_one_or_none()
    if customer and customer.stripe_customer_id:
        return customer

    org_result = await db.execute(select(Organization).where(Organization.id == organization_id))
    organization = org_result.scalar_one_or_none()

    stripe_customer = stripe.Customer.create(
        email=current_user.email,
        name=organization.name if organization else current_user.full_name or current_user.email,
        metadata={
            "organization_id": str(organization_id),
            "user_id": str(current_user.id),
            "app": "finveille",
        },
    )

    if not customer:
        customer = BillingCustomer(
            organization_id=organization_id,
            stripe_customer_id=stripe_customer.id,
            billing_email=current_user.email,
            metadata_json={"created_from": "checkout"},
        )
        db.add(customer)
    else:
        customer.stripe_customer_id = stripe_customer.id
        customer.billing_email = current_user.email
    await db.commit()
    await db.refresh(customer)
    return customer


async def _upsert_subscription_from_stripe(db: AsyncSession, stripe_subscription) -> Subscription | None:
    metadata = _obj_get(stripe_subscription, "metadata", {}) or {}
    organization_id = metadata.get("organization_id")
    customer_id = _obj_get(stripe_subscription, "customer", None)

    if not organization_id and customer_id:
        customer_result = await db.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == customer_id)
        )
        customer = customer_result.scalar_one_or_none()
        organization_id = str(customer.organization_id) if customer else None

    if not organization_id:
        return None

    items = _obj_get(stripe_subscription, "items", None)
    items_data = _obj_get(items, "data", []) if items else []
    first_item = items_data[0] if items_data else None
    price = _obj_get(first_item, "price", None) if first_item else None
    price_id = _obj_get(price, "id", None) if price else None
    plan = await _get_plan_by_price(db, price_id)
    if not plan:
        plan_result = await db.execute(select(Plan).where(Plan.slug == "free"))
        plan = plan_result.scalar_one_or_none()
    if not plan:
        return None

    result = await db.execute(select(Subscription).where(Subscription.organization_id == _uuid(organization_id)))
    subscription = result.scalar_one_or_none()
    values = {
        "plan_id": plan.id,
        "status": _obj_get(stripe_subscription, "status", "active"),
        "stripe_subscription_id": _obj_get(stripe_subscription, "id"),
        "current_period_start": _dt(_obj_get(stripe_subscription, "current_period_start", None)),
        "current_period_end": _dt(_obj_get(stripe_subscription, "current_period_end", None)),
    }

    if subscription:
        for field, value in values.items():
            setattr(subscription, field, value)
    else:
        subscription = Subscription(organization_id=_uuid(organization_id), **values)
        db.add(subscription)

    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plan).where(Plan.is_active == True).order_by(Plan.sort_order.asc()))
    return list(result.scalars().all())


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = await get_billing_context(db, current_user)
    return SubscriptionResponse(
        plan=context.plan,
        subscription_status=context.subscription.status if context.subscription else "free",
        organization_id=context.organization_id,
        current_period_end=context.subscription.current_period_end if context.subscription else None,
        usage=context.usage,
        limits=context.plan.limits or {},
        features=context.plan.features or {},
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    data: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Plan).where(Plan.slug == data.plan_slug, Plan.is_active == True))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan introuvable.")
    if plan.slug == "free":
        return CheckoutResponse(
            checkout_url="/billing",
            configured=True,
            message="Le plan Free ne necessite pas de paiement.",
        )
    if not plan.stripe_price_id:
        raise HTTPException(status_code=503, detail=f"stripe_price_id manquant pour le plan {plan.slug}.")

    organization_id = await get_current_organization_id(db, current_user)
    if not organization_id:
        raise HTTPException(status_code=400, detail="Creez une organisation avant de souscrire a un plan.")

    stripe = _stripe()
    customer = await _get_or_create_customer(db, stripe, organization_id, current_user)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer.stripe_customer_id,
        client_reference_id=str(organization_id),
        line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
        success_url=settings.STRIPE_CHECKOUT_SUCCESS_URL + "&session_id={CHECKOUT_SESSION_ID}",
        cancel_url=settings.STRIPE_CHECKOUT_CANCEL_URL,
        allow_promotion_codes=True,
        metadata={"organization_id": str(organization_id), "plan_slug": plan.slug},
        subscription_data={"metadata": {"organization_id": str(organization_id), "plan_slug": plan.slug}},
    )

    await record_usage(
        db,
        current_user,
        "billing_checkout_started",
        organization_id=organization_id,
        metadata={"plan": plan.slug, "stripe_checkout_session_id": session.id},
    )
    return CheckoutResponse(checkout_url=session.url, configured=True, message="Session Stripe Checkout creee.")


@router.post("/portal", response_model=BillingPortalResponse)
async def open_billing_portal(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await get_current_organization_id(db, current_user)
    if not organization_id:
        raise HTTPException(status_code=400, detail="Aucune organisation active.")

    stripe = _stripe()
    customer = await _get_or_create_customer(db, stripe, organization_id, current_user)
    session = stripe.billing_portal.Session.create(
        customer=customer.stripe_customer_id,
        return_url=settings.STRIPE_PORTAL_RETURN_URL,
    )
    return BillingPortalResponse(portal_url=session.url, configured=True, message="Portail Stripe cree.")


@router.post("/admin/sync-products")
async def sync_stripe_products(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
):
    stripe = _stripe()
    result = await db.execute(select(Plan).where(Plan.is_active == True).order_by(Plan.sort_order.asc()))
    plans = list(result.scalars().all())
    synced = []

    for plan in plans:
        if plan.slug == "free" or plan.price_monthly_eur <= 0:
            synced.append({"plan": plan.slug, "skipped": True, "reason": "no_paid_price"})
            continue
        if plan.stripe_price_id:
            synced.append({"plan": plan.slug, "stripe_price_id": plan.stripe_price_id, "skipped": True})
            continue

        product = stripe.Product.create(
            name=f"FinVeille {plan.name}",
            description=plan.description,
            metadata={"plan_slug": plan.slug, "app": "finveille"},
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=int(plan.price_monthly_eur) * 100,
            currency=(plan.currency or "EUR").lower(),
            recurring={"interval": "month"},
            metadata={"plan_slug": plan.slug, "app": "finveille"},
        )
        plan.stripe_price_id = price.id
        synced.append({"plan": plan.slug, "product_id": product.id, "stripe_price_id": price.id})

    await db.commit()
    return {"synced": synced}


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    stripe = _stripe()
    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    if settings.STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Signature Stripe invalide : {exc}") from exc
    else:
        event = await request.json()

    event_type = event.get("type", "unknown")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        organization_id = (data.get("metadata") or {}).get("organization_id") or data.get("client_reference_id")
        if customer_id and organization_id:
            result = await db.execute(select(BillingCustomer).where(BillingCustomer.organization_id == _uuid(organization_id)))
            customer = result.scalar_one_or_none()
            if not customer:
                db.add(BillingCustomer(organization_id=_uuid(organization_id), stripe_customer_id=customer_id, metadata_json={"created_from": "webhook"}))
            else:
                customer.stripe_customer_id = customer_id
            await db.commit()
        if subscription_id:
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)
            await _upsert_subscription_from_stripe(db, stripe_subscription)

    if event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        await _upsert_subscription_from_stripe(db, data)

    if event_type == "invoice.payment_failed":
        subscription_id = data.get("subscription")
        if subscription_id:
            result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == subscription_id))
            subscription = result.scalar_one_or_none()
            if subscription:
                subscription.status = "past_due"
                await db.commit()

    return {"received": True, "type": event_type}
