"""API smoke on a database populated only by Alembic migrations."""
import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import AsyncSessionLocal, engine
from app.main import app
from app.models.device import Device
from app.services.notification_service import NotificationService
import app.schema_readiness as schema_readiness


pytestmark = pytest.mark.asyncio
MIGRATED_URL = os.getenv("TEST_POSTGRES_DATABASE_URL")
UNREADY_URL = os.getenv("TEST_UNREADY_POSTGRES_URL")


@pytest.mark.skipif(not MIGRATED_URL, reason="Dedicated migrated PostgreSQL test URL required")
async def test_signup_login_organization_profile_project_and_device_without_startup_ddl(monkeypatch):
    monkeypatch.setattr(NotificationService, "notify_admin_new_user", lambda **_kwargs: None)
    monkeypatch.setattr(NotificationService, "send_welcome_email", lambda **_kwargs: False)
    async with engine.connect() as connection:
        before = set((await connection.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        ))).scalars())
    async with app.router.lifespan_context(app):
        pass

    email = f"lot2-{uuid4()}@example.org"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/ready")).status_code == 200
        registered = await client.post("/api/v1/auth/register", json={
            "email": email, "password": "Lot2-secret-123", "full_name": "Lot 2 Test",
        })
        assert registered.status_code == 201, registered.text
        token = registered.json()["access_token"]
        logged_in = await client.post("/api/v1/auth/login", json={
            "email": email, "password": "Lot2-secret-123",
        })
        assert logged_in.status_code == 200, logged_in.text
        headers = {"Authorization": f"Bearer {token}"}
        assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200
        profile = await client.patch("/api/v1/auth/me", headers=headers, json={
            "country": "France", "sectors": "energie,climat",
        })
        assert profile.status_code == 200, profile.text
        assert profile.json()["country"] == "France"
        assert (await client.get("/api/v1/organizations/current", headers=headers)).status_code == 200
        organization = await client.post("/api/v1/organizations", headers=headers, json={"name": "Second Org"})
        assert organization.status_code == 201, organization.text
        org_profile = await client.put("/api/v1/me/profile", headers=headers, json={
            "organization_type": "association", "countries": ["France"],
        })
        assert org_profile.status_code == 200, org_profile.text
        project = await client.post("/api/v1/funding-projects", headers=headers, json={"name": "Projet test"})
        assert project.status_code == 201, project.text
        assert (await client.get("/api/v1/funding-projects", headers=headers)).status_code == 200

        device = Device(
            title="Lot 2 grant", organism="Test", country="France",
            device_type="subvention", source_url="https://example.org/lot2",
        )
        async with AsyncSessionLocal() as session:
            session.add(device)
            await session.commit()
        async with engine.connect() as connection:
            assert (await connection.execute(text(
                "SELECT search_vector IS NOT NULL FROM devices WHERE id = :id"
            ), {"id": device.id})).scalar_one()
        fetched = await client.get(f"/api/v1/devices/{device.id}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["title"] == "Lot 2 grant"

    async with engine.connect() as connection:
        after = set((await connection.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        ))).scalars())
    assert after == before


@pytest.mark.skipif(not UNREADY_URL, reason="Dedicated unmigrated PostgreSQL test URL required")
async def test_readiness_rejects_unmigrated_schema(monkeypatch):
    unready_engine = create_async_engine(UNREADY_URL)
    monkeypatch.setattr(schema_readiness, "engine", unready_engine)
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            assert (await client.get("/api/health")).status_code == 200
            response = await client.get("/api/ready")
            assert response.status_code == 503
    finally:
        await unready_engine.dispose()
