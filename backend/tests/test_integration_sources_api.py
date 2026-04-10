from sqlalchemy import text


def test_sources_crud_and_logs_with_sqlite(integration_client):
    client, session_factory = integration_client

    create_response = client.post(
        "/api/v1/sources/",
        json={
            "name": "Source Integration",
            "organism": "Test Org",
            "country": "France",
            "source_type": "portail_officiel",
            "category": "public",
            "level": 1,
            "url": "https://example.org/source",
            "collection_mode": "manual",
            "check_frequency": "daily",
            "reliability": 4,
            "is_active": True,
            "config": {},
        },
    )

    assert create_response.status_code == 201
    source_id = create_response.json()["id"]

    list_response = client.get("/api/v1/sources/?category=public")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert any(item["id"] == source_id for item in payload)

    test_response = client.post(
        "/api/v1/sources/test",
        json={
            "name": "Source Integration",
            "organism": "Test Org",
            "country": "France",
            "source_type": "portail_officiel",
            "category": "public",
            "level": 1,
            "url": "https://example.org/source",
            "collection_mode": "manual",
            "check_frequency": "daily",
            "reliability": 4,
            "is_active": True,
            "config": {},
        },
    )
    assert test_response.status_code == 200
    assert test_response.json()["success"] is True
    assert test_response.json()["can_activate"] is True

    update_response = client.put(f"/api/v1/sources/{source_id}", json={"is_active": False, "notes": "Desactivee pour test"})
    assert update_response.status_code == 200
    assert update_response.json()["is_active"] is False

    import asyncio

    async def seed_log():
        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO collection_logs (
                        id, source_id, status, items_found, items_new, items_updated, items_skipped, items_error, error_message
                    ) VALUES (
                        :id, :source_id, 'failed', 0, 0, 0, 0, 1, 'Erreur de test sqlite'
                    )
                    """
                ),
                {"id": "log-test-1", "source_id": source_id},
            )
            await session.commit()

    asyncio.run(seed_log())

    logs_response = client.get(f"/api/v1/sources/{source_id}/logs")
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) >= 1
    assert logs[0]["error_message"] == "Erreur de test sqlite"
