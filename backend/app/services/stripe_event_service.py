"""Apply verified Stripe events atomically and in event-created order."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingCheckout, BillingCustomer, Plan, StripeWebhookEvent, Subscription
from app.models.organization import Organization
from app.services.billing_service import KNOWN_PLANS


SUBSCRIPTION_EVENTS = frozenset({
    "customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted",
})
INVOICE_EVENTS = frozenset({"invoice.payment_failed", "invoice.payment_succeeded", "invoice.paid"})
RELEVANT_EVENTS = SUBSCRIPTION_EVENTS | INVOICE_EVENTS | {"checkout.session.completed"}
TERMINAL_STATUSES = frozenset({"canceled", "incomplete_expired"})
KNOWN_STATUSES = frozenset({
    "active", "trialing", "past_due", "unpaid", "incomplete", "incomplete_expired", "canceled", "paused",
})


def value(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def timestamp(value_to_convert):
    return datetime.fromtimestamp(int(value_to_convert), tz=timezone.utc) if value_to_convert else None


def subscription_price_id(item):
    items = value(value(item, "items", {}), "data", []) or []
    price = value(items[0], "price", None) if items else None
    return value(price, "id", None) if price else None


async def process_stripe_event(db: AsyncSession, stripe, event) -> str:
    event_id = value(event, "id")
    event_created = value(event, "created")
    event_type = value(event, "type", "unknown")
    if not event_id or not isinstance(event_created, int) or event_created <= 0:
        raise HTTPException(status_code=400, detail="Événement Stripe incomplet.")
    if event_type not in RELEVANT_EVENTS:
        return "ignored_type"

    data = value(value(event, "data", {}), "object", {}) or {}
    stripe_sub_id = value(data, "id") if event_type in SUBSCRIPTION_EVENTS else (
        value(data, "subscription") or value(value(value(data, "parent", {}), "subscription_details", {}), "subscription")
    )
    customer_id = value(data, "customer")
    if not stripe_sub_id or not customer_id:
        return "ignored_incomplete"

    # A signed event is not, by itself, authorization to choose a tenant.
    # Customer ownership must already have been established by checkout.
    customer = (await db.execute(select(BillingCustomer).where(
        BillingCustomer.stripe_customer_id == customer_id,
    ))).scalar_one_or_none()
    if not customer:
        return "ignored_customer"
    metadata = value(data, "metadata", {}) or {}
    claimed_org = value(metadata, "organization_id") or (
        value(data, "client_reference_id") if event_type == "checkout.session.completed" else None
    )
    if claimed_org and str(claimed_org) != str(customer.organization_id):
        return "ignored_tenant_mismatch"

    # The organization row serializes concurrent webhook deliveries and
    # checkout. The ledger, subscription and checkout marker commit together.
    await db.execute(select(Organization.id).where(
        Organization.id == customer.organization_id,
    ).with_for_update())
    if (await db.execute(select(StripeWebhookEvent.id).where(StripeWebhookEvent.id == event_id))).scalar_one_or_none():
        return "duplicate"

    subscription = (await db.execute(select(Subscription).where(
        Subscription.organization_id == customer.organization_id,
    ))).scalar_one_or_none()
    if subscription and subscription.last_stripe_event_created is not None and event_created < subscription.last_stripe_event_created:
        outcome = "stale"
    elif subscription and subscription.stripe_subscription_id not in (None, stripe_sub_id) and subscription.status not in TERMINAL_STATUSES:
        outcome = "subscription_conflict"
    else:
        outcome = "applied"
        same_second = bool(subscription and subscription.last_stripe_event_created == event_created)
        # Stripe timestamps have one-second precision. For a tie, never trust
        # arrival order or lexicographic event IDs: read current Stripe state.
        try:
            canonical = stripe.Subscription.retrieve(stripe_sub_id) if same_second else None
        except Exception:
            canonical = None
        if same_second and canonical is None:
            subscription.status = "paused"  # uncertainty cannot retain premium
            outcome = "tie_unresolved"
        elif event_type == "invoice.payment_failed" and not same_second:
            if not subscription or subscription.stripe_subscription_id != stripe_sub_id or subscription.status in TERMINAL_STATUSES:
                outcome = "ignored_subscription"
            else:
                subscription.status = "past_due"
        else:
            snapshot = canonical if same_second else (data if event_type in SUBSCRIPTION_EVENTS else stripe.Subscription.retrieve(stripe_sub_id))
            if value(snapshot, "id") != stripe_sub_id or value(snapshot, "customer") != customer_id:
                outcome = "ignored_subscription"
            else:
                snapshot_metadata = value(snapshot, "metadata", {}) or {}
                snapshot_org = value(snapshot_metadata, "organization_id")
                if snapshot_org and str(snapshot_org) != str(customer.organization_id):
                    outcome = "ignored_tenant_mismatch"
                else:
                    price_id = subscription_price_id(snapshot)
                    plan = (await db.execute(select(Plan).where(
                        Plan.stripe_price_id == price_id, Plan.is_active.is_(True),
                    ))).scalar_one_or_none() if price_id else None
                    if not plan or plan.slug not in KNOWN_PLANS or plan.slug == "free":
                        outcome = "ignored_price"
                        if subscription and subscription.stripe_subscription_id == stripe_sub_id:
                            subscription.status = "paused"
                    else:
                        stripe_status = "canceled" if event_type == "customer.subscription.deleted" else value(snapshot, "status")
                        if stripe_status not in KNOWN_STATUSES:
                            outcome = "ignored_status"
                            if subscription and subscription.stripe_subscription_id == stripe_sub_id:
                                subscription.status = "paused"
                        elif subscription and subscription.stripe_subscription_id == stripe_sub_id and subscription.status in TERMINAL_STATUSES and stripe_status not in TERMINAL_STATUSES:
                            outcome = "terminal_reuse"
                        else:
                            if not subscription:
                                subscription = Subscription(organization_id=customer.organization_id)
                                db.add(subscription)
                            subscription.stripe_subscription_id = stripe_sub_id
                            subscription.plan_id = plan.id
                            subscription.status = stripe_status
                            subscription.current_period_start = timestamp(value(snapshot, "current_period_start"))
                            subscription.current_period_end = timestamp(value(snapshot, "current_period_end"))
                            subscription.cancel_at_period_end = bool(value(snapshot, "cancel_at_period_end", False))
        # Restrictive uncertainty also advances the local clock: an older
        # delivery must not restore premium after an unknown price or status.
        if outcome in {"applied", "ignored_price", "ignored_status", "tie_unresolved"} and subscription:
            subscription.last_stripe_event_created = event_created
            subscription.last_stripe_event_id = event_id
            if outcome == "applied" and event_type == "checkout.session.completed":
                checkout = (await db.execute(select(BillingCheckout).where(
                    BillingCheckout.organization_id == customer.organization_id,
                ))).scalar_one_or_none()
                if checkout and checkout.stripe_session_id == value(data, "id"):
                    await db.delete(checkout)

    db.add(StripeWebhookEvent(
        id=event_id, event_type=event_type, stripe_created=event_created,
        outcome=outcome, stripe_subscription_id=stripe_sub_id,
    ))
    await db.commit()
    return outcome
