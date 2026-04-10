import asyncio
from datetime import datetime, timezone

from sqlalchemy import text


def test_match_prefers_high_quality_source_on_sqlite(integration_client):
    client, session_factory = integration_client

    now = datetime.now(timezone.utc).isoformat()

    async def seed_data():
        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO sources (
                        id, name, organism, country, source_type, level, url, collection_mode,
                        check_frequency, reliability, category, is_active, consecutive_errors,
                        last_success_at, created_at, updated_at
                    ) VALUES
                    (
                        'src-good', 'Source fiable', 'Org A', 'France', 'portail_officiel', 1, 'https://good.example',
                        'api', 'daily', 5, 'public', 1, 0, :recent_success, :created_at, :updated_at
                    ),
                    (
                        'src-bad', 'Source fragile', 'Org B', 'France', 'portail_officiel', 1, 'https://bad.example',
                        'api', 'daily', 2, 'public', 0, 4, :old_success, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "recent_success": now,
                    "old_success": "2024-01-01T00:00:00+00:00",
                    "created_at": now,
                    "updated_at": now,
                },
            )

            await session.execute(
                text(
                    """
                    INSERT INTO devices (
                        id, title, organism, country, device_type, short_description, source_url, source_id,
                        validation_status, status, last_verified_at, updated_at, created_at
                    ) VALUES
                    (
                        'dev-good', 'Fonds seed fintech France', 'Org A', 'France', 'investissement',
                        'Investissement seed pour startup fintech paiement', 'https://good.example/device',
                        'src-good', 'approved', 'open', :recent_success, :updated_at, :created_at
                    ),
                    (
                        'dev-bad', 'Fonds seed fintech France bis', 'Org B', 'France', 'investissement',
                        'Investissement seed pour startup fintech paiement', 'https://bad.example/device',
                        'src-bad', 'approved', 'open', :old_success, :updated_at, :created_at
                    )
                    """
                ),
                {
                    "recent_success": now,
                    "old_success": "2024-01-01T00:00:00+00:00",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            await session.commit()

    asyncio.run(seed_data())

    response = client.post(
        "/api/v1/match/?limit=5",
        files={"file": ("pitch.txt", b"startup fintech de paiement en recherche d'investissement seed en France", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["matches"]) >= 1
    assert payload["matches"][0]["id"] == "dev-good"
