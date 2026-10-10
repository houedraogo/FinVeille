"""Base PostgreSQL jetable pour les tests d'intégration du nettoyage du catalogue.

Active uniquement si TEST_PG_URL est défini (ex. postgresql+asyncpg://user:pw@host:5432/postgres) :
chaque test reçoit sa propre base créée puis supprimée. Sans TEST_PG_URL les tests sont ignorés,
comme les autres tests PostgreSQL du dépôt.
"""
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401  (enregistre toutes les tables)
from app.database import Base

PG_URL = os.getenv("TEST_PG_URL")
requires_pg = pytest.mark.skipif(not PG_URL, reason="TEST_PG_URL requis (PostgreSQL jetable)")


def _admin_sync_url() -> str:
    base = PG_URL.rsplit("/", 1)[0]
    return base.replace("postgresql+asyncpg://", "postgresql://", 1) + "/postgres"


@pytest_asyncio.fixture
async def pg_session_factory():
    if not PG_URL:
        pytest.skip("TEST_PG_URL requis")
    name = "kafundo_p1_" + uuid4().hex[:16]
    admin = create_engine(_admin_sync_url(), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {name}"))
    engine = create_async_engine(PG_URL.rsplit("/", 1)[0] + "/" + name)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        admin.dispose()


def make_device(**overrides):
    """Fiche minimale valide pour les tests."""
    from app.models.device import Device

    values = dict(
        title="Aide test", title_normalized="aide test", organism="Org test", country="France",
        device_type="subvention", source_url="https://exemple.fr/aide-test", status="open",
        validation_status="auto_published", ai_rewrite_status="pending", slug=f"aide-{uuid4().hex[:10]}",
        source_hash=uuid4().hex,
    )
    values.update(overrides)
    return Device(**values)
