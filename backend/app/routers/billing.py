from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.billing import BillingCheckout, BillingCustomer, Plan, Subscription
from app.models.organization import Organization
from app.models.user import User
from app.schemas.billing import (
    BillingPortalResponse,
    CheckoutRequest,
    CheckoutResponse,
    PlanResponse,
    SubscriptionResponse,
)
from app.services.billing_service import get_billing_context, record_usage
from app.services.stripe_event_service import process_stripe_event, value
from app.services.tenant_access import require_tenant

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


async def _get_or_create_customer(
    db: AsyncSession,
    stripe,
    organization_id,
    current_user: User,
    *,
    commit: bool = True,
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
            "app": "kafundo",
        },
        idempotency_key=f"kafundo-customer-{organization_id}",
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
    if commit:
        await db.commit()
        await db.refresh(customer)
    else:
        await db.flush()
    return customer




@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plan).where(Plan.is_active == True).order_by(Plan.sort_order.asc()))
    return list(result.scalars().all())


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_tenant(db, current_user)
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
    organization_id = await require_tenant(db, current_user, "billing")
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

    stripe = _stripe()
    await db.execute(select(Organization.id).where(Organization.id == organization_id).with_for_update())
    existing = (await db.execute(select(Subscription).where(
        Subscription.organization_id == organization_id,
    ))).scalar_one_or_none()
    if existing and existing.status not in {"canceled", "incomplete_expired"}:
        current_plan = (await db.execute(select(Plan).where(Plan.id == existing.plan_id))).scalar_one_or_none()
        if existing.stripe_subscription_id or not current_plan or current_plan.slug != "free":
            raise HTTPException(status_code=409, detail="Un abonnement existe déjà ; utilisez le portail de facturation.")

    pending = (await db.execute(select(BillingCheckout).where(
        BillingCheckout.organization_id == organization_id,
    ))).scalar_one_or_none()
    customer = await _get_or_create_customer(db, stripe, organization_id, current_user, commit=False)
    # A stale local row cannot authorize a second remote paid subscription.
    remote = stripe.Subscription.list(customer=customer.stripe_customer_id, status="all", limit=100)
    if value(remote, "has_more", False):
        raise HTTPException(status_code=409, detail="Historique Stripe à réconcilier avant checkout.")
    if any(value(item, "status") not in {"canceled", "incomplete_expired"} for item in (value(remote, "data", []) or [])):
        raise HTTPException(status_code=409, detail="Un abonnement Stripe existe déjà ; utilisez le portail.")
    if pending and pending.expires_at > datetime.now(timezone.utc):
        if pending.plan_id != plan.id:
            raise HTTPException(status_code=409, detail="Un checkout est déjà en cours pour un autre plan.")
        return CheckoutResponse(checkout_url=pending.checkout_url, configured=True, message="Session Stripe Checkout existante.")
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
        idempotency_key=f"kafundo-{organization_id}-{plan.id}-{uuid4()}",
    )
    expires = value(session, "expires_at")
    expires_at = datetime.fromtimestamp(expires, timezone.utc) if expires else datetime.now(timezone.utc) + timedelta(minutes=30)
    if pending:
        pending.plan_id = plan.id
        pending.stripe_session_id = session.id
        pending.checkout_url = session.url
        pending.expires_at = expires_at
    else:
        db.add(BillingCheckout(
            organization_id=organization_id, plan_id=plan.id,
            stripe_session_id=session.id, checkout_url=session.url, expires_at=expires_at,
        ))

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
    organization_id = await require_tenant(db, current_user, "billing")

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
            name=f"Kafundo {plan.name}",
            description=plan.description,
            metadata={"plan_slug": plan.slug, "app": "kafundo"},
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=int(plan.price_monthly_eur) * 100,
            currency=(plan.currency or "EUR").lower(),
            recurring={"interval": "month"},
            metadata={"plan_slug": plan.slug, "app": "kafundo"},
        )
        plan.stripe_price_id = price.id
        synced.append({"plan": plan.slug, "product_id": product.id, "stripe_price_id": price.id})

    await db.commit()
    return {"synced": synced}


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook Stripe non configuré.")
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Signature Stripe requise.")
    stripe = _stripe()
    try:
        event = stripe.Webhook.construct_event(await request.body(), signature, settings.STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Signature Stripe invalide.") from exc
    outcome = await process_stripe_event(db, stripe, event)
    return {"received": True, "type": value(event, "type", "unknown"), "outcome": outcome}
