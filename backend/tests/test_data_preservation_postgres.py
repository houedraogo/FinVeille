"""Regression tests for destructive enrichment and device merges on PostgreSQL."""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.device import Device
from app.models.device_history import DeviceHistory
from app.models.relevance import DeviceRelevanceCache
from app.models.organization import Organization
from app.models.user import User
from app.models.workspace import DevicePipeline, FavoriteDevice
from app.services.dedup_service import DedupService
from app.services.device_service import DeviceService
from app.tasks import quality_tasks


TEST_URL = os.environ.get("TEST_POSTGRES_DATABASE_URL")
pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(not TEST_URL, reason="Dedicated PostgreSQL test URL required")]


async def persisted(db, model, row_id):
    return await db.get(model, row_id, populate_existing=True)


@pytest.fixture
async def db():
    engine = create_async_engine(TEST_URL)
    async with engine.connect() as connection:
        outer = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
            yield session
        await outer.rollback()
    await engine.dispose()


async def devices(db):
    canonical = Device(title="Funding", title_normalized="funding", organism="Org", country="FR", device_type="subvention", source_url="https://example.org/a", short_description="thin")
    duplicate = Device(title="Funding", title_normalized="funding", organism="Org", country="FR", device_type="subvention", source_url="https://example.org/b", short_description="thin", amount_max=1000)
    db.add_all([canonical, duplicate])
    await db.commit()
    return canonical, duplicate


async def user_and_organization(db):
    user = User(email=f"test-{uuid4()}@example.org", password_hash="test", role="reader")
    org = Organization(name=f"Test {uuid4()}", slug=f"test-{uuid4()}")
    db.add_all([user, org])
    await db.commit()
    return user, org


@pytest.mark.parametrize("failure", [
    "connect_timeout", "read_timeout", "dns", 403, 404, 429, 500,
    "empty", "javascript", "thin_text", "parse_error",
])
async def test_enrichment_never_deletes_device_or_pipeline_on_unusable_page(db, monkeypatch, failure):
    device, _ = await devices(db)
    user, _ = await user_and_organization(db)
    device.last_verified_at = datetime.now(timezone.utc) - timedelta(days=10)
    pipeline = DevicePipeline(user_id=user.id, device_id=device.id, pipeline_status="soumis", note="Client work", documents=[{"name": "proposal.pdf"}])
    db.add(pipeline)
    await db.commit()

    @asynccontextmanager
    async def fresh_db():
        yield db

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url):
            request = httpx.Request("GET", url)
            if failure == "connect_timeout":
                raise httpx.ConnectTimeout("timeout", request=request)
            if failure == "read_timeout":
                raise httpx.ReadTimeout("timeout", request=request)
            if failure == "dns":
                raise httpx.ConnectError("DNS", request=request)
            if isinstance(failure, int):
                return httpx.Response(failure, request=request)
            body = {
                "empty": "",
                "javascript": "<script>window.app = true</script>",
                "thin_text": "<p>Short content</p>",
            }.get(failure, "<p>Some content that cannot be parsed.</p>")
            return httpx.Response(200, text=body, request=request)

    monkeypatch.setattr(quality_tasks, "_fresh_db", fresh_db)
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    if failure == "parse_error":
        def fail_parse(_soup):
            raise ValueError("malformed page")
        monkeypatch.setattr(quality_tasks, "_extract_scraped_sections", fail_parse)
    await quality_tasks._enrich_missing_async(batch_size=1)
    assert await persisted(db, Device, device.id) is not None
    retained = await persisted(db, DevicePipeline, pipeline.id)
    assert retained is not None
    assert retained.note == "Client work"
    assert retained.documents == [{"name": "proposal.pdf"}]


async def test_merge_without_user_relations(db):
    canonical, duplicate = await devices(db)
    result = await DedupService(db).merge_group(str(canonical.id), [str(duplicate.id)])
    assert result["deleted"] == 1
    assert await persisted(db, Device, duplicate.id) is None
    assert (await persisted(db, Device, canonical.id)).amount_max == 1000


async def test_merge_transfers_pipeline_with_all_fields(db):
    canonical, duplicate = await devices(db)
    user, org = await user_and_organization(db)
    pipeline = DevicePipeline(user_id=user.id, organization_id=org.id, device_id=duplicate.id, pipeline_status="soumis", priority="haute", note="Important", documents=[{"name": "proposal.pdf"}], snapshot={"source": "client"})
    db.add(pipeline)
    await db.commit()
    await DedupService(db).merge_group(str(canonical.id), [str(duplicate.id)])
    retained = await persisted(db, DevicePipeline, pipeline.id)
    assert retained.device_id == canonical.id
    assert (retained.pipeline_status, retained.note, retained.priority) == ("soumis", "Important", "haute")
    assert retained.documents == [{"name": "proposal.pdf"}]
    assert retained.snapshot == {"source": "client"}


async def test_merge_conflicting_pipeline_keeps_both_devices_and_records(db):
    canonical, duplicate = await devices(db)
    user, _ = await user_and_organization(db)
    first = DevicePipeline(user_id=user.id, device_id=canonical.id, pipeline_status="brouillon", note="A")
    second = DevicePipeline(user_id=user.id, device_id=duplicate.id, pipeline_status="soumis", note="B", documents=[{"name": "b.pdf"}])
    db.add_all([first, second])
    await db.commit()
    canonical_id, duplicate_id, first_id, second_id = canonical.id, duplicate.id, first.id, second.id
    with pytest.raises(ValueError):
        await DedupService(db).merge_group(str(canonical_id), [str(duplicate_id)])
    assert await persisted(db, Device, duplicate_id) is not None
    assert (await persisted(db, DevicePipeline, first_id)).note == "A"
    assert (await persisted(db, DevicePipeline, second_id)).note == "B"


async def test_merge_transfers_favorite_history_and_relevance(db):
    canonical, duplicate = await devices(db)
    user, org = await user_and_organization(db)
    favorite = FavoriteDevice(user_id=user.id, device_id=duplicate.id, snapshot={"saved": True})
    history = DeviceHistory(device_id=duplicate.id, changed_by="system", change_type="updated", diff={"x": 1})
    cache = DeviceRelevanceCache(device_id=duplicate.id, organization_id=org.id, relevance_score=80)
    db.add_all([favorite, history, cache])
    await db.commit()
    await DedupService(db).merge_group(str(canonical.id), [str(duplicate.id)])
    assert (await persisted(db, FavoriteDevice, favorite.id)).device_id == canonical.id
    assert (await persisted(db, DeviceHistory, history.id)).device_id == canonical.id
    assert (await persisted(db, DeviceRelevanceCache, cache.id)).device_id == canonical.id
    assert (await persisted(db, FavoriteDevice, favorite.id)).snapshot == {"saved": True}


async def test_merge_rolls_back_on_mid_transfer_failure(db, monkeypatch):
    canonical, duplicate = await devices(db)
    user, _ = await user_and_organization(db)
    favorite = FavoriteDevice(user_id=user.id, device_id=duplicate.id)
    db.add(favorite)
    await db.commit()
    canonical_id, duplicate_id, favorite_id = canonical.id, duplicate.id, favorite.id
    from app.services import dedup_service
    original = dedup_service._merge_fields

    def fail_after_field_change(a, b):
        original(a, b)
        raise RuntimeError("injected failure")

    monkeypatch.setattr(dedup_service, "_merge_fields", fail_after_field_change)
    with pytest.raises(RuntimeError):
        await DedupService(db).merge_group(str(canonical_id), [str(duplicate_id)])
    assert await persisted(db, Device, duplicate_id) is not None
    assert (await persisted(db, Device, canonical_id)).amount_max is None
    assert (await persisted(db, FavoriteDevice, favorite_id)).device_id == duplicate_id


async def test_merge_refuses_favorite_and_cache_conflicts(db):
    canonical, duplicate = await devices(db)
    user, org = await user_and_organization(db)
    db.add_all([
        FavoriteDevice(user_id=user.id, device_id=canonical.id, snapshot={"side": "A"}),
        FavoriteDevice(user_id=user.id, device_id=duplicate.id, snapshot={"side": "B"}),
        DeviceRelevanceCache(device_id=canonical.id, organization_id=org.id, relevance_score=10),
        DeviceRelevanceCache(device_id=duplicate.id, organization_id=org.id, relevance_score=90),
    ])
    await db.commit()
    duplicate_id, user_id, org_id = duplicate.id, user.id, org.id
    with pytest.raises(ValueError):
        await DedupService(db).merge_group(str(canonical.id), [str(duplicate.id)])
    assert await persisted(db, Device, duplicate_id) is not None
    assert len((await db.execute(select(FavoriteDevice).where(FavoriteDevice.user_id == user_id))).scalars().all()) == 2
    assert len((await db.execute(select(DeviceRelevanceCache).where(DeviceRelevanceCache.organization_id == org_id))).scalars().all()) == 2


async def test_auto_merge_skips_ambiguous_group_and_merges_safe_group(db):
    canonical, duplicate = await devices(db)
    canonical.completeness_score = 100
    duplicate.completeness_score = 50
    user, _ = await user_and_organization(db)
    db.add_all([
        DevicePipeline(user_id=user.id, device_id=canonical.id, pipeline_status="brouillon", note="A"),
        DevicePipeline(user_id=user.id, device_id=duplicate.id, pipeline_status="soumis", note="B"),
    ])
    safe_a = Device(title="Safe", title_normalized="safe", organism="Org", country="FR", device_type="subvention", source_url="https://example.org/safe-a", completeness_score=100)
    safe_b = Device(title="Safe", title_normalized="safe", organism="Org", country="FR", device_type="subvention", source_url="https://example.org/safe-b", completeness_score=50)
    db.add_all([safe_a, safe_b])
    await db.commit()
    duplicate_id, safe_b_id, user_id = duplicate.id, safe_b.id, user.id
    result = await DedupService(db).merge_duplicates_auto()
    assert result["merged_groups"] >= 1
    assert result["skipped_groups"] >= 1
    assert await persisted(db, Device, duplicate_id) is not None
    assert await persisted(db, Device, safe_b_id) is None
    assert len((await db.execute(select(DevicePipeline).where(DevicePipeline.user_id == user_id))).scalars().all()) == 2


async def test_merge_refuses_unmapped_database_foreign_key(db):
    canonical, duplicate = await devices(db)
    await db.execute(text("CREATE TABLE lot1_extra_device_ref (device_id uuid REFERENCES devices(id) ON DELETE CASCADE)"))
    await db.execute(text("INSERT INTO lot1_extra_device_ref (device_id) VALUES (:device_id)"), {"device_id": duplicate.id})
    await db.commit()
    canonical_id, duplicate_id = canonical.id, duplicate.id
    with pytest.raises(ValueError, match="Relations de dispositif non prises en charge"):
        await DedupService(db).merge_group(str(canonical_id), [str(duplicate_id)])
    assert await persisted(db, Device, duplicate_id) is not None
    assert (await db.execute(text("SELECT count(*) FROM lot1_extra_device_ref"))).scalar_one() == 1


async def test_quality_purge_keeps_device_with_client_pipeline(db):
    device, _ = await devices(db)
    user, _ = await user_and_organization(db)
    device.validation_status = "pending_review"
    pipeline = DevicePipeline(user_id=user.id, device_id=device.id, pipeline_status="soumis", note="Client work")
    db.add(pipeline)
    await db.commit()
    result = await DeviceService(db).purge_unenrichable_devices(actor_id="admin", dry_run=False)
    assert result["deleted"] == 0
    assert await persisted(db, Device, device.id) is not None
    assert (await persisted(db, DevicePipeline, pipeline.id)).note == "Client work"


async def test_quality_purge_still_removes_unreferenced_thin_device(db):
    device, _ = await devices(db)
    device.validation_status = "pending_review"
    await db.commit()
    device_id = device.id
    result = await DeviceService(db).purge_unenrichable_devices(actor_id="admin", dry_run=False)
    assert result["deleted"] == 1
    assert result["protected"] == 0
    assert await persisted(db, Device, device_id) is None
