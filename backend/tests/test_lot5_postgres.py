"""Lot 5 regressions on disposable PostgreSQL; no live Redis or SMTP."""
import os
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, text, update, or_

from app.database import AsyncSessionLocal, engine
from app.main import app
from app.models.alert import Alert, AlertDelivery
from app.models.device import Device
from app.models.operations import EmailEvent
from app.models.organization import Invitation, Organization, OrganizationMember
from app.models.source import Source
from app.models.user import User
from app.services.alert_service import AlertService
from app.services.dedup_service import DedupService
from app.services.device_service import DeviceService
from app.tasks import alert_tasks
from app.tasks.celery_app import celery_app
from app.collector.pipeline import CollectionPipeline
from app.collector.base_connector import CollectionResult, RawItem
from app.utils.auth_utils import create_access_token

pytestmark = [pytest.mark.asyncio(loop_scope="module"), pytest.mark.skipif(
    os.getenv("KAFUNDO_LOT5_TESTS") != "1" or not os.getenv("TEST_POSTGRES_DATABASE_URL"),
    reason="Disposable Lot 5 PostgreSQL required",
)]


def device(nonce, suffix, *, seen=None, close=None, title="Transition energie"):
    return Device(title=f"{title} {suffix} {nonce}", organism="Lot5", country="France",
                  device_type="subvention", status="open", validation_status="approved",
                  source_url=f"https://example.org/{nonce}/{suffix}",
                  short_description="Financement de la transition énergétique",
                  first_seen_at=seen, close_date=close)


async def test_celery_routes_without_publishing():
    from celery import Celery
    from kombu import Connection

    routes = {name: celery_app.amqp.router.route(entry.get("options", {}), entry["task"])["queue"].name
              for name, entry in celery_app.conf.beat_schedule.items()}
    assert len(routes) == 19
    assert set(routes.values()) == {"collect", "alerts", "default"}
    assert list(routes.values()).count("default") == 14
    assert celery_app.amqp.router.route({}, "unrouted.task")["queue"].name == "default"
    isolated = Celery("lot5-routing", broker="memory://")
    isolated.conf.update(task_default_queue="default", task_routes=celery_app.conf.task_routes)
    expected = {
        "default": "app.tasks.quality_tasks.update_expired_devices",
        "collect": "app.tasks.collect_tasks.collect_by_level",
        "alerts": "app.tasks.alert_tasks.send_daily_alerts",
    }
    for task in expected.values():
        isolated.send_task(task)
    with Connection("memory://") as connection:
        assert {queue: connection.SimpleQueue(queue).get(block=False).headers["task"]
                for queue in expected} == expected


async def test_alert_frequency_matching_recovery_and_smtp(monkeypatch):
    nonce = uuid4().hex[:10]
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await db.execute(update(Alert).where(or_(Alert.name.like("instant-%"), Alert.name.like("daily-%"),
                                                 Alert.name.like("weekly-%"))).values(is_active=False))
        user = User(email=f"lot5-alert-{nonce}@example.org", password_hash="unused", role="reader")
        db.add(user)
        await db.flush()
        org = Organization(name="Alert test", slug=f"alert-{nonce}", created_by_id=user.id)
        db.add(org)
        await db.flush()
        user.default_organization_id = org.id
        db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="org_owner"))
        old = device(nonce, "old", seen=now - timedelta(days=1))
        old.title = f"Transition {nonce}"
        no_keyword = device(nonce, "wrong", seen=now - timedelta(hours=1), title="Agriculture")
        no_keyword.title = "Agriculture uniquement"
        no_keyword.short_description = "Financement agricole"
        expired = device(nonce, "expired", seen=now - timedelta(hours=1), close=date.today() - timedelta(days=1))
        db.add_all([old, no_keyword, expired])
        await db.flush()
        instant = Alert(user_id=user.id, organization_id=org.id, name=f"instant-{nonce}",
                        frequency="instant", channels=["email"], alert_types=["new"], is_active=True,
                        criteria={"keywords": [nonce]}, created_at=now - timedelta(days=2))
        daily = Alert(user_id=user.id, organization_id=org.id, name=f"daily-{nonce}",
                      frequency="daily", channels=["email"], is_active=True,
                      criteria={"keywords": [nonce]})
        weekly = Alert(user_id=user.id, organization_id=org.id, name=f"weekly-{nonce}",
                       frequency="weekly", channels=["email"], is_active=True,
                       criteria={"keywords": [nonce]})
        db.add_all([instant, daily, weekly])
        await db.commit()
        ids = (instant.id, daily.id, weekly.id, old.id)

    monkeypatch.setattr("app.services.notification_service.NotificationService.send_email", lambda **kwargs: False)
    await alert_tasks._send_new_opportunity_alerts_async(2)
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(func.count()).select_from(AlertDelivery).where(AlertDelivery.alert_id == ids[0]))).scalar_one() == 0
        assert (await db.get(Alert, ids[0])).last_triggered_at is None

    sent = []
    monkeypatch.setattr("app.services.notification_service.NotificationService.send_email", lambda **kwargs: sent.append(kwargs) or True)
    await alert_tasks._send_new_opportunity_alerts_async(2)
    await alert_tasks._send_new_opportunity_alerts_async(2)
    assert len(sent) == 1
    async with AsyncSessionLocal() as db:
        deliveries = (await db.execute(select(AlertDelivery).where(AlertDelivery.alert_id == ids[0]))).scalars().all()
        assert [item.device_id for item in deliveries] == [ids[3]]
        assert (await db.get(Alert, ids[0])).last_triggered_at is not None
        svc = AlertService(db)
        assert {d.id for d in await svc.match_devices(await db.get(Alert, ids[1]))} == {ids[3]}

    await alert_tasks._send_daily_alerts_async()
    assert len(sent) == 3  # daily and weekly, never instant again
    await alert_tasks._send_daily_alerts_async()
    assert len(sent) == 3
    async with AsyncSessionLocal() as db:
        for alert_id in ids[:3]:
            alert = await db.get(Alert, alert_id)
            assert alert.last_triggered_at is not None
            alert.is_active = False
        await db.commit()


async def test_pipeline_business_hash_and_sql_savepoint(monkeypatch):
    nonce = uuid4().hex[:10]
    source = {"id": str(uuid4()), "name": "Test", "organism": "Lot5", "country": "France",
              "url": "https://example.org", "level": 2, "config": {}}
    async with AsyncSessionLocal() as db:
        db.add(Source(id=source["id"], name="Test", organism="Lot5", country="France",
                      source_type="institution_publique", url=source["url"], collection_mode="manual"))
        existing = device(nonce, "business", seen=datetime.now(timezone.utc))
        db.add(existing)
        await db.commit()
        existing_id = existing.id
    normalized = {"title": existing.title, "short_description": existing.short_description,
                  "organism": "Lot5", "country": "France", "source_url": existing.source_url,
                  "device_type": "subvention", "status": "open", "close_date": date.today() + timedelta(days=30),
                  "amount_max": 1000, "currency": "EUR"}
    async with AsyncSessionLocal() as db:
        pipeline = CollectionPipeline(db, source)
        monkeypatch.setattr(pipeline.normalizer, "normalize", lambda _raw: normalized.copy())
        monkeypatch.setattr(pipeline.deduplicator, "find_duplicate", lambda _norm: db.get(Device, existing_id))
        raw = RawItem(title="business", url="https://example.org", raw_content="contenu")
        assert await pipeline._process_item(raw) == "updated"
        await db.commit()
        normalized["amount_max"] = 2000
        assert await pipeline._process_item(raw) == "updated"
        await db.commit()
        normalized["close_date"] += timedelta(days=1)
        assert await pipeline._process_item(raw) == "updated"
        await db.commit()
        assert await pipeline._process_item(raw) == "skipped"
        await db.commit()
        assert (await db.get(Device, existing_id)).amount_max == 2000

    async with AsyncSessionLocal() as db:
        pipeline = CollectionPipeline(db, source)
        async def item(raw):
            if raw.title == "B":
                await db.execute(text("SELECT 1/0"))
            db.add(device(nonce, raw.title))
            return "new"
        monkeypatch.setattr(pipeline, "_process_item", item)
        batch = CollectionResult(source_id=source["id"], success=True, items=[
            RawItem(title=title, url="https://example.org", raw_content="") for title in "ABC"
        ])
        stats = await pipeline.process(batch)
        assert stats["new"] == 2 and stats["errors"] == 1
        assert (await db.execute(select(func.count()).select_from(Device).where(Device.title.like(f"%{nonce}")))).scalar_one() == 3


async def test_delivery_survives_device_merge_and_protects_purge():
    nonce = uuid4().hex[:10]
    async with AsyncSessionLocal() as db:
        user = User(email=f"lot5-merge-{nonce}@example.org", password_hash="unused", role="reader")
        db.add(user)
        await db.flush()
        canonical = device(nonce, "canonical")
        duplicate = device(nonce, "duplicate")
        db.add_all([canonical, duplicate])
        db.add(Alert(user_id=user.id, name=f"merged-{nonce}", frequency="instant",
                     channels=["email"], alert_types=["new"], is_active=False))
        await db.flush()
        alert = (await db.execute(select(Alert).where(Alert.name == f"merged-{nonce}"))).scalar_one()
        db.add_all([AlertDelivery(alert_id=alert.id, device_id=canonical.id),
                    AlertDelivery(alert_id=alert.id, device_id=duplicate.id)])
        await db.commit()
        canonical_id, duplicate_id, alert_id = canonical.id, duplicate.id, alert.id
        assert (await DedupService(db).merge_group(str(canonical_id), [str(duplicate_id)]))["deleted"] == 1
        rows = (await db.execute(select(AlertDelivery).where(AlertDelivery.alert_id == alert_id))).scalars().all()
        assert len(rows) == 1 and rows[0].device_id == canonical_id
        surviving = await db.get(Device, canonical_id)
        surviving.validation_status = "pending_review"
        await db.commit()
        preview = await DeviceService(db).purge_unenrichable_devices(dry_run=True)
        assert any(row["id"] == str(canonical_id) and row["protected"] for row in preview["preview"])


async def test_invitation_valid_invalid_expired_wrong_user_and_personal_org():
    nonce = uuid4().hex[:10]
    async with AsyncSessionLocal() as db:
        owner = User(email=f"lot5-owner-{nonce}@example.org", password_hash="unused", role="reader")
        invited = User(email=f"lot5-invited-{nonce}@example.org", password_hash="unused", role="reader")
        wrong = User(email=f"lot5-wrong-{nonce}@example.org", password_hash="unused", role="reader")
        db.add_all([owner, invited, wrong])
        await db.flush()
        org = Organization(name="Inviting", slug=f"inviting-{nonce}", created_by_id=owner.id)
        personal = Organization(name="Personal", slug=f"personal-{nonce}", created_by_id=invited.id)
        db.add_all([org, personal])
        await db.flush()
        invited.default_organization_id = personal.id
        db.add(OrganizationMember(organization_id=personal.id, user_id=invited.id, role="org_owner"))
        valid = Invitation(organization_id=org.id, email=invited.email, role="member", token=f"valid-{nonce}")
        expired = Invitation(organization_id=org.id, email=invited.email, role="member", token=f"expired-{nonce}",
                             expires_at=datetime.now(timezone.utc) - timedelta(days=1))
        db.add_all([valid, expired])
        await db.commit()
        org_id, personal_id, invited_id, wrong_id = org.id, personal.id, invited.id, wrong.id
    def headers(user_id):
        return {"Authorization": f"Bearer {create_access_token(str(user_id), 'reader')}"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        path = "/api/v1/organizations/invitations/"
        assert (await client.post(path + f"missing-{nonce}/accept", headers=headers(invited_id))).status_code == 404
        assert (await client.post(path + f"expired-{nonce}/accept", headers=headers(invited_id))).status_code == 400
        assert (await client.post(path + f"valid-{nonce}/accept", headers=headers(wrong_id))).status_code == 403
        accepted = await client.post(path + f"valid-{nonce}/accept", headers=headers(invited_id))
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["organization_id"] == str(org_id)
        assert (await client.post(path + f"valid-{nonce}/accept", headers=headers(invited_id))).status_code == 400
        assert (await client.post(f"/api/v1/organizations/{org_id}/select", headers=headers(invited_id))).status_code == 200
    async with AsyncSessionLocal() as db:
        memberships = (await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == invited_id))).scalars().all()
        assert {membership.organization_id for membership in memberships} == {org_id, personal_id}
        assert (await db.get(User, invited_id)).default_organization_id == org_id
    await engine.dispose()
