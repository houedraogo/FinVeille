import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.models.collection_log import CollectionLog
from app.models.device import Device
from app.models.source import Source


def test_quality_audit_endpoint_reports_expected_flags(integration_client):
    client, session_factory = integration_client
    source_id = uuid4()

    async def seed():
        async with session_factory() as session:
            source = Source(
                id=source_id,
                name="Source récente bruitée",
                organism="Organisme test",
                country="France",
                source_type="portail_officiel",
                level=1,
                url="https://example.org/source",
                collection_mode="html",
                check_frequency="daily",
                reliability=3,
                category="public",
                is_active=True,
                consecutive_errors=2,
                created_at=datetime.now(timezone.utc) - timedelta(days=3),
            )
            weak_device = Device(
                id=uuid4(),
                title="Fiche pauvre",
                organism="Organisme test",
                country="France",
                device_type="subvention",
                status="open",
                source_url="https://example.org/device-1",
                source_id=source_id,
                short_description="Court",
            )
            api_device = Device(
                id=uuid4(),
                title="URL technique",
                organism="Organisme test",
                country="France",
                device_type="subvention",
                status="open",
                source_url="https://api.example.org/v1/aide/123",
                source_id=source_id,
                short_description="Description exploitable",
            )
            stale_open = Device(
                id=uuid4(),
                title="Ouvert mais expiré",
                organism="Organisme test",
                country="France",
                device_type="subvention",
                status="open",
                source_url="https://example.org/device-2",
                source_id=source_id,
                short_description="Description exploitable",
                close_date=date.today() - timedelta(days=2),
            )
            noisy_log = CollectionLog(
                id=uuid4(),
                source_id=source_id,
                status="failed",
                items_found=25,
                items_new=0,
                items_updated=0,
                items_error=12,
                started_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
            session.add_all([source, weak_device, api_device, stale_open, noisy_log])
            await session.commit()

    asyncio.run(seed())

    response = client.get("/api/v1/admin/quality/audit")

    assert response.status_code == 200
    payload = response.json()
    assert payload["weak_devices"]["count"] >= 1
    assert payload["non_public_urls"]["count"] >= 1
    assert payload["open_with_past_close_date"]["count"] >= 1
    assert payload["noisy_recent_sources"]["count"] >= 1
