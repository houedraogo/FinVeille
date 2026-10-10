"""R9: a device created without a source currency is stored with a NULL currency (not 'EUR') on PostgreSQL."""
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.schemas.device import DeviceCreate
from app.services.device_service import DeviceService

TEST_URL = os.environ.get("TEST_POSTGRES_DATABASE_URL")
pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(not TEST_URL, reason="Dedicated PostgreSQL test URL required")]


@pytest.fixture
async def db():
    engine = create_async_engine(TEST_URL)
    async with engine.connect() as connection:
        outer = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
            yield session
        await outer.rollback()
    await engine.dispose()


def _device(**overrides):
    base = dict(title="Aide sans montant SQ12", organism="Org", country="International", device_type="subvention",
                source_url="https://example.org/sq12-null-currency", short_description="Aide sans montant ni devise dans la source.")
    base.update(overrides)
    return DeviceCreate(**base)


async def _stored_currency(db, device_id):
    return (await db.execute(text("SELECT currency FROM devices WHERE id = :id"), {"id": device_id})).scalar_one()


async def test_pipeline_creation_path_stores_null_currency(db):
    device = await DeviceService(db).create(_device(), created_by="system", commit=False)
    assert await _stored_currency(db, device.id) is None


async def test_a_currency_written_in_the_source_is_stored(db):
    device = await DeviceService(db).create(_device(title="Aide avec devise SQ12", source_url="https://example.org/sq12-eur", amount_max=50000, currency="EUR"),
                                            created_by="system", commit=False)
    assert await _stored_currency(db, device.id) == "EUR"
