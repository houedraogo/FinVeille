"""Stripe is mocked; authorization and quota transactions use disposable PostgreSQL."""
import asyncio
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
import stripe
from sqlalchemy import func, select

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.main import app
from app.models.alert import Alert
from app.models.billing import BillingCheckout, BillingCustomer, Plan, StripeWebhookEvent, Subscription
from app.models.device import Device
from app.models.organization import Organization, OrganizationMember
from app.models.project import UserProject
from app.models.relevance import OrganizationProfile
from app.models.user import User
from app.services.billing_service import DEFAULT_PLANS, ensure_default_plans
from app.utils.auth_utils import create_access_token


pytestmark = [
    pytest.mark.asyncio(loop_scope="module"),
    pytest.mark.skipif(
        os.getenv("KAFUNDO_BILLING_TESTS") != "1" or not os.getenv("TEST_POSTGRES_DATABASE_URL"),
        reason="Disposable PostgreSQL billing database required",
    ),
]


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(str(user.id), user.role)}"}


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def scenario():
    assert engine.url.database.startswith("kafundo_lot4_")
    nonce = uuid4().hex[:12]
    async with AsyncSessionLocal() as db:
        await ensure_default_plans(db)
        plans = {p.slug: p for p in (await db.execute(select(Plan))).scalars().all()}
        for slug in ("pro", "team", "expert", "enterprise"):
            plans[slug].stripe_price_id = f"price_lot4_{slug}_{nonce}"
        users = {role: User(email=f"lot4-{role}-{nonce}@example.org", password_hash="unused", role="admin" if role == "internal" else "reader", full_name=role)
                 for role in ("owner", "admin", "member", "viewer", "outsider", "internal")}
        db.add_all(users.values())
        await db.flush()
        org = Organization(name=f"Billing {nonce}", slug=f"billing-{nonce}", created_by_id=users["owner"].id)
        quota_org = Organization(name=f"Quota {nonce}", slug=f"quota-{nonce}", created_by_id=users["outsider"].id)
        db.add_all([org, quota_org])
        await db.flush()
        for role in ("owner", "admin", "member", "viewer", "internal"):
            users[role].default_organization_id = org.id
            db.add(OrganizationMember(organization_id=org.id, user_id=users[role].id, role="org_owner" if role == "owner" else ("org_admin" if role == "admin" else ("member" if role == "internal" else role))))
        users["outsider"].default_organization_id = quota_org.id
        db.add(OrganizationMember(organization_id=quota_org.id, user_id=users["outsider"].id, role="org_owner"))
        db.add(BillingCustomer(organization_id=org.id, stripe_customer_id=f"cus_{nonce}"))
        db.add(Subscription(organization_id=org.id, plan_id=plans["free"].id, status="active"))
        db.add(Subscription(organization_id=quota_org.id, plan_id=plans["free"].id, status="active"))
        db.add(OrganizationProfile(organization_id=org.id, countries=["France"]))
        device = Device(title=f"Lot4 device {nonce}", organism="Test", country="France", device_type="subvention", status="open", source_url=f"https://example.org/{nonce}", validation_status="approved")
        db.add(device)
        await db.flush()
        project = UserProject(user_id=users["owner"].id, organization_id=org.id, name="Paid matching history",
                              cached_matches=[{"id": str(device.id), "title": device.title, "score": 88, "days_left": None, "amount_max": 100}])
        db.add(project)
        await db.commit()
    return SimpleNamespace(nonce=nonce, users=users, org=org, quota_org=quota_org, plans=plans,
                           customer=f"cus_{nonce}", subscription=f"sub_{nonce}", device=device, project=project)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as value:
        yield value
    await engine.dispose()


@pytest.fixture
def fake_stripe(monkeypatch):
    calls = {"checkout": 0, "retrieve": 0, "list": 0}
    snapshots = {}
    remote = []

    class SubscriptionAPI:
        @staticmethod
        def retrieve(subscription_id, **_):
            calls["retrieve"] += 1
            return snapshots[subscription_id]

        @staticmethod
        def list(**_kwargs):
            calls["list"] += 1
            return {"data": remote, "has_more": False}

    class CheckoutAPI:
        @staticmethod
        def create(**_kwargs):
            calls["checkout"] += 1
            return SimpleNamespace(id=f"cs_{calls['checkout']}", url=f"https://checkout.example/{calls['checkout']}",
                                   expires_at=int(time.time()) + 1800)

    fake = SimpleNamespace(
        Webhook=stripe.Webhook, Subscription=SubscriptionAPI,
        checkout=SimpleNamespace(Session=CheckoutAPI),
        Customer=SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(id=f"cus_new_{uuid4().hex}")),
        billing_portal=SimpleNamespace(Session=SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(url="https://portal.example"))),
        snapshots=snapshots, remote=remote, calls=calls,
    )
    monkeypatch.setattr("app.routers.billing._stripe", lambda: fake)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_lot4_fake")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_lot4_fake")
    return fake


def snapshot(scenario, *, status="active", price="pro", subscription_id=None, cancel_at_period_end=False,
             period_end=None, customer=None):
    now = int(time.time())
    return {
        "id": subscription_id or scenario.subscription,
        "customer": customer or scenario.customer,
        "metadata": {"organization_id": str(scenario.org.id)},
        "status": status,
        "items": {"data": [{"price": {"id": scenario.plans[price].stripe_price_id}}]},
        "current_period_start": now - 3600,
        "current_period_end": period_end if period_end is not None else now + 3600,
        "cancel_at_period_end": cancel_at_period_end,
    }


def signed_event(scenario, *, event_type="customer.subscription.updated", created=None, data=None, event_id=None, secret="whsec_lot4_fake"):
    body = json.dumps({
        "id": event_id or f"evt_{uuid4().hex}", "created": created or int(time.time()),
        "type": event_type, "data": {"object": data or snapshot(scenario)},
    }, separators=(",", ":")).encode()
    timestamp = int(time.time())
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"stripe-signature": f"t={timestamp},v1={digest}"}


async def post_event(client, scenario, **kwargs):
    body, headers = signed_event(scenario, **kwargs)
    return await client.post("/api/v1/billing/webhook/stripe", content=body, headers=headers)


async def test_signature_fail_closed_and_valid_event(client, scenario, fake_stripe, monkeypatch):
    body, headers = signed_event(scenario, data=snapshot(scenario))
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    assert (await client.post("/api/v1/billing/webhook/stripe", content=body)).status_code == 503
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_lot4_fake")
    assert (await client.post("/api/v1/billing/webhook/stripe", content=body)).status_code == 400
    assert (await client.post("/api/v1/billing/webhook/stripe", content=body, headers={"stripe-signature": "t=1,v1=bad"})).status_code == 400
    assert (await client.post("/api/v1/billing/webhook/stripe", content=body + b" ", headers=headers)).status_code == 400
    assert (await client.post("/api/v1/billing/webhook/stripe", content=body, headers=headers)).json()["outcome"] == "applied"
    async with AsyncSessionLocal() as db:
        sub = (await db.execute(select(Subscription).where(Subscription.organization_id == scenario.org.id))).scalar_one()
        assert sub.status == "active" and sub.plan_id == scenario.plans["pro"].id


async def test_order_duplicates_cancellation_and_recovery(client, scenario, fake_stripe):
    base = int(time.time()) + 100
    active = snapshot(scenario, status="active")
    canceled = snapshot(scenario, status="canceled")
    assert (await post_event(client, scenario, created=base, data=active, event_id=f"evt_active_{scenario.nonce}")).json()["outcome"] == "applied"
    assert (await post_event(client, scenario, created=base + 20, data=canceled, event_id=f"evt_cancel_{scenario.nonce}")).json()["outcome"] == "applied"
    assert (await post_event(client, scenario, created=base + 20, data=canceled, event_id=f"evt_cancel_{scenario.nonce}")).json()["outcome"] == "duplicate"
    assert (await post_event(client, scenario, created=base + 22, data=active)).json()["outcome"] == "terminal_reuse"
    assert (await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))).json()["plan"]["slug"] == "free"
    reactivated_id = f"sub_reactivated_{scenario.nonce}"
    reactivated = snapshot(scenario, status="active", subscription_id=reactivated_id)
    concurrent_body, concurrent_headers = signed_event(scenario, created=base + 25, data=reactivated)
    concurrent = await asyncio.gather(*(
        client.post("/api/v1/billing/webhook/stripe", content=concurrent_body, headers=concurrent_headers)
        for _ in range(2)
    ))
    assert sorted(response.json()["outcome"] for response in concurrent) == ["applied", "duplicate"]
    assert (await post_event(client, scenario, created=base + 10, data=active)).json()["outcome"] == "stale"
    scenario.subscription = reactivated_id
    active = reactivated
    assert (await post_event(client, scenario, created=base + 30, data=active)).json()["outcome"] == "applied"
    failed = {"subscription": scenario.subscription, "customer": scenario.customer}
    assert (await post_event(client, scenario, event_type="invoice.payment_failed", created=base + 40, data=failed)).json()["outcome"] == "applied"
    assert (await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))).json()["plan"]["slug"] == "free"
    fake_stripe.snapshots[scenario.subscription] = active
    assert (await post_event(client, scenario, event_type="invoice.payment_succeeded", created=base + 50, data=failed)).json()["outcome"] == "applied"
    assert (await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))).json()["plan"]["slug"] == "pro"
    assert (await post_event(client, scenario, event_type="invoice.payment_failed", created=base + 52, data=failed)).json()["outcome"] == "applied"
    assert (await post_event(client, scenario, event_type="invoice.paid", created=base + 54, data=failed)).json()["outcome"] == "applied"
    assert (await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))).json()["plan"]["slug"] == "pro"
    ending = snapshot(scenario, status="active", cancel_at_period_end=True)
    assert (await post_event(client, scenario, created=base + 60, data=ending)).json()["outcome"] == "applied"
    assert (await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))).json()["plan"]["slug"] == "pro"
    expired = snapshot(scenario, status="active", cancel_at_period_end=True, period_end=int(time.time()) - 1)
    assert (await post_event(client, scenario, created=base + 70, data=expired)).json()["outcome"] == "applied"
    assert (await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))).json()["plan"]["slug"] == "free"
    assert (await post_event(client, scenario, created=base + 80, data=active)).json()["outcome"] == "applied"
    assert (await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))).json()["plan"]["slug"] == "pro"
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(func.count(StripeWebhookEvent.id)).where(StripeWebhookEvent.id == f"evt_cancel_{scenario.nonce}"))).scalar_one() == 1


async def test_foreign_subscription_unknown_event_and_status_matrix(client, scenario, fake_stripe):
    base = int(time.time()) + 200
    other = snapshot(scenario, subscription_id=f"sub_foreign_{scenario.nonce}")
    assert (await post_event(client, scenario, created=base, data=other)).json()["outcome"] == "subscription_conflict"
    assert (await post_event(client, scenario, event_type="some.unknown.event", created=base + 1)).json()["outcome"] == "ignored_type"
    fake_stripe.snapshots[scenario.subscription] = snapshot(scenario, status="past_due")
    assert (await post_event(client, scenario, created=base + 1, data=snapshot(scenario, status="active"))).json()["outcome"] == "applied"
    assert (await post_event(client, scenario, created=base + 1, data=snapshot(scenario, status="active"))).json()["outcome"] == "applied"
    assert (await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))).json()["plan"]["slug"] == "free"
    assert (await post_event(client, scenario, created=base + 2, data=snapshot(scenario, status="active"))).json()["outcome"] == "applied"
    assert (await post_event(client, scenario, created=base + 3, data=snapshot(scenario, status="unrecognized"))).json()["outcome"] == "ignored_status"
    assert (await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))).json()["plan"]["slug"] == "free"
    unknown_price = snapshot(scenario, status="active")
    unknown_price["items"]["data"][0]["price"]["id"] = "price_unknown"
    assert (await post_event(client, scenario, created=base + 4, data=unknown_price)).json()["outcome"] == "ignored_price"
    assert (await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))).json()["plan"]["slug"] == "free"
    for offset, status in enumerate(("trialing", "past_due", "unpaid", "incomplete", "paused", "unrecognized", "incomplete_expired", "canceled"), 6):
        data = snapshot(scenario, status=status)
        outcome = (await post_event(client, scenario, created=base + offset, data=data)).json()["outcome"]
        assert outcome == ("ignored_status" if status == "unrecognized" else "applied")
        response = await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))
        assert response.json()["plan"]["slug"] == ("pro" if status == "trialing" else "free")


async def test_paid_period_end_and_checkout_rbac(client, scenario, fake_stripe):
    paid_sub_id = f"sub_paid_{scenario.nonce}"
    assert (await post_event(client, scenario, created=int(time.time()) + 499,
                             data=snapshot(scenario, status="active", subscription_id=paid_sub_id))).json()["outcome"] == "applied"
    scenario.subscription = paid_sub_id
    # All terminal statuses allow a new checkout; only the owner may create it.
    assert (await client.post("/api/v1/billing/checkout", headers=auth(scenario.users["owner"]), json={"plan_slug": "team"})).status_code == 409
    assert (await post_event(client, scenario, created=int(time.time()) + 500, data=snapshot(scenario, status="canceled"))).json()["outcome"] == "applied"
    for role in ("admin", "member", "viewer"):
        assert (await client.post("/api/v1/billing/checkout", headers=auth(scenario.users[role]), json={"plan_slug": "team"})).status_code == 403
        assert (await client.post("/api/v1/billing/portal", headers=auth(scenario.users[role]))).status_code == 403
    assert (await client.post("/api/v1/billing/checkout", json={"plan_slug": "team"})).status_code == 401
    assert (await client.post("/api/v1/billing/checkout", headers=auth(scenario.users["owner"]), json={"plan_slug": "team", "stripe_price_id": "price_forged", "amount": 1})).status_code == 422
    first = await client.post("/api/v1/billing/checkout", headers=auth(scenario.users["owner"]), json={"plan_slug": "team"})
    assert first.status_code == 200, first.text
    second = await client.post("/api/v1/billing/checkout", headers=auth(scenario.users["owner"]), json={"plan_slug": "team"})
    assert second.status_code == 200 and second.json()["checkout_url"] == first.json()["checkout_url"]
    assert fake_stripe.calls["checkout"] == 1
    assert (await client.post("/api/v1/billing/checkout", headers=auth(scenario.users["owner"]), json={"plan_slug": "expert"})).status_code == 409
    async with AsyncSessionLocal() as db:
        checkout = (await db.execute(select(BillingCheckout).where(BillingCheckout.organization_id == scenario.org.id))).scalar_one()
        checkout.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
    for remote_status in ("active", "trialing", "past_due", "unpaid", "incomplete", "paused", "unknown"):
        fake_stripe.remote[:] = [{"status": remote_status}]
        assert (await client.post("/api/v1/billing/checkout", headers=auth(scenario.users["owner"]), json={"plan_slug": "team"})).status_code == 409
    assert fake_stripe.calls["checkout"] == 1
    fake_stripe.remote[:] = [{"status": "incomplete_expired"}]
    assert (await client.post("/api/v1/billing/checkout", headers=auth(scenario.users["owner"]), json={"plan_slug": "team"})).status_code == 200
    assert fake_stripe.calls["checkout"] == 2
    checkout_sub_id = f"sub_checkout_{scenario.nonce}"
    fake_stripe.snapshots[checkout_sub_id] = snapshot(scenario, price="team", subscription_id=checkout_sub_id)
    completed = {
        "id": "cs_2", "customer": scenario.customer, "subscription": checkout_sub_id,
        "metadata": {"organization_id": str(scenario.org.id)}, "client_reference_id": str(scenario.org.id),
    }
    event = await post_event(client, scenario, event_type="checkout.session.completed", created=int(time.time()) + 600, data=completed)
    assert event.json()["outcome"] == "applied"
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(func.count(BillingCheckout.organization_id)).where(BillingCheckout.organization_id == scenario.org.id))).scalar_one() == 0
        sub = (await db.execute(select(Subscription).where(Subscription.organization_id == scenario.org.id))).scalar_one()
        assert sub.plan_id == scenario.plans["team"].id
        assert sub.stripe_subscription_id == checkout_sub_id
    assert (await client.post("/api/v1/billing/checkout", headers=auth(scenario.users["owner"]), json={"plan_slug": "expert"})).status_code == 409


async def test_plan_features_and_unknown_plan_fail_closed(client, scenario, monkeypatch):
    async def matched(*_args, **_kwargs):
        return {"profile": {}, "matches": []}
    monkeypatch.setattr("app.routers.match.match_project", matched)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    async with AsyncSessionLocal() as db:
        sub = (await db.execute(select(Subscription).where(Subscription.organization_id == scenario.org.id))).scalar_one()
        sub.stripe_subscription_id = None
        sub.status = "active"
        for definition in DEFAULT_PLANS:
            sub.plan_id = scenario.plans[definition["slug"]].id
            await db.commit()
            response = await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))
            assert response.json()["features"] == definition["features"]
            assert response.json()["limits"] == definition["limits"]
            export = await client.get("/api/v1/devices/export/csv", params={"q": f"no-results-{scenario.nonce}"}, headers=auth(scenario.users["owner"]))
            assert export.status_code == (200 if definition["features"]["exports"] else 402)
            matching = await client.post("/api/v1/match/", headers=auth(scenario.users["owner"]), files={"file": ("pitch.txt", b"test", "text/plain")})
            assert matching.status_code == (200 if definition["features"]["matching_ai"] else 402)
            history = await client.get(f"/api/v1/projects/{scenario.project.id}", headers=auth(scenario.users["owner"]))
            assert len(history.json()["cached_matches"]) == (1 if definition["features"]["matching_ai"] else 0)
            relevance = await client.get(f"/api/v1/devices/{scenario.device.id}/relevance", headers=auth(scenario.users["owner"]))
            assert relevance.status_code == (200 if definition["features"]["smart_scoring"] else 402)
            detail = await client.get(f"/api/v1/devices/{scenario.device.id}", headers=auth(scenario.users["owner"]))
            assert detail.status_code == 200
            assert (detail.json()["relevance_score"] > 0) == bool(definition["features"]["smart_scoring"])
            custom = await client.post("/api/v1/alerts/", headers=auth(scenario.users["owner"]), json={
                "name": "Custom alert", "criteria": {"countries": ["France"]},
            })
            assert custom.status_code == (201 if definition["features"]["custom_alerts"] else 402)
            if custom.status_code == 201:
                assert (await client.delete(f"/api/v1/alerts/{custom.json()['id']}", headers=auth(scenario.users["owner"]))).status_code == 204
            analysis = await client.post(f"/api/v1/devices/{scenario.device.id}/analyze", headers=auth(scenario.users["internal"]))
            assert analysis.status_code == (503 if definition["features"]["advanced_analysis"] else 402)
        unknown = Plan(slug=f"unknown-{scenario.nonce}", name="Unknown", limits={"alerts": -1}, features={"exports": True}, price_monthly_eur=1)
        db.add(unknown)
        await db.flush()
        sub.plan_id = unknown.id
        await db.commit()
    response = await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))
    assert response.json()["plan"]["slug"] == "free"
    assert (await client.get("/api/v1/devices/export/csv", headers=auth(scenario.users["owner"]))).status_code == 402


async def test_free_quota_is_serialized_across_concurrent_requests(client, scenario):
    request_headers = auth(scenario.users["outsider"])
    responses = await asyncio.gather(*(
        client.post("/api/v1/alerts/", headers=request_headers, json={"name": f"Quota {i}", "criteria": {}})
        for i in range(8)
    ))
    statuses = [response.status_code for response in responses]
    assert statuses.count(201) == 3, [(response.status_code, response.text) for response in responses]
    assert statuses.count(402) == 5
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(func.count(Alert.id)).where(Alert.organization_id == scenario.quota_org.id))).scalar_one() == 3


async def test_quota_is_shared_by_tenant_members(client, scenario):
    responses = await asyncio.gather(*(
        client.post("/api/v1/alerts/", headers=auth(scenario.users["owner" if i % 2 else "admin"]),
                    json={"name": f"Shared quota {i}", "criteria": {}})
        for i in range(8)
    ))
    assert [response.status_code for response in responses].count(201) == 3
    assert [response.status_code for response in responses].count(402) == 5
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(func.count(Alert.id)).where(Alert.organization_id == scenario.org.id))).scalar_one() == 3


async def test_checkout_entitlement_requires_valid_period(client, scenario, fake_stripe):
    """FAIL CLOSED: current_period_end absent → premium not granted; present and future → granted."""
    base = int(time.time()) + 2000
    entitlement_sub_id = f"sub_entitlement_{scenario.nonce}"

    # Put current subscription in terminal state to allow a new one
    cancel_r = await post_event(client, scenario, created=base,
                                data=snapshot(scenario, status="canceled",
                                              subscription_id=scenario.subscription))
    assert cancel_r.json()["outcome"] in ("applied", "stale", "terminal_reuse", "duplicate")

    # Retrieve mock returns snapshot WITHOUT current_period_end — simulates API v2025 behavior
    snap_no_period = {
        "id": entitlement_sub_id,
        "customer": scenario.customer,
        "metadata": {"organization_id": str(scenario.org.id)},
        "status": "active",
        "items": {"data": [{"price": {"id": scenario.plans["pro"].stripe_price_id}}]},
        "cancel_at_period_end": False,
        # current_period_start and current_period_end intentionally absent
    }
    fake_stripe.snapshots[entitlement_sub_id] = snap_no_period

    completed_no_period = {
        "id": f"cs_entitlement_nop_{scenario.nonce}", "customer": scenario.customer,
        "subscription": entitlement_sub_id,
        "metadata": {"organization_id": str(scenario.org.id)},
        "client_reference_id": str(scenario.org.id),
    }
    r = await post_event(client, scenario, event_type="checkout.session.completed",
                         created=base + 1, data=completed_no_period)
    assert r.json()["outcome"] == "applied"

    # FAIL CLOSED: no current_period_end → billing service denies premium
    resp = await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))
    assert resp.json()["plan"]["slug"] == "free"

    # Now send a subscription event with a valid future current_period_end
    now = int(time.time())
    snap_with_period = snapshot(scenario, status="active", price="pro",
                                subscription_id=entitlement_sub_id, period_end=now + 86400)
    r2 = await post_event(client, scenario, event_type="customer.subscription.updated",
                          created=base + 2, data=snap_with_period)
    assert r2.json()["outcome"] == "applied"

    # Valid period → premium granted
    resp2 = await client.get("/api/v1/billing/subscription", headers=auth(scenario.users["owner"]))
    assert resp2.json()["plan"]["slug"] == "pro"

    scenario.subscription = entitlement_sub_id
