from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.dependencies import get_current_user
from app.main import app
from app.database import Base


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type, _compiler, **_kw):
    return "TEXT"


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(_type, _compiler, **_kw):
    return "TEXT"


@compiles(TSVECTOR, "sqlite")
def _compile_tsvector_sqlite(_type, _compiler, **_kw):
    return "TEXT"


async def override_current_user():
    return SimpleNamespace(
        id="test-user",
        email="admin@finveille.com",
        full_name="Admin Test",
        role="admin",
        is_active=True,
    )


async def override_db():
    yield None


@pytest.fixture
def client():
    from app.database import get_db

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def integration_client(tmp_path: Path):
    from app.database import get_db

    db_path = tmp_path / f"test-{uuid4().hex}.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_sqlite_db():
        async with session_factory() as session:
            yield session

    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    import asyncio

    asyncio.run(init_db())

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_sqlite_db

    with TestClient(app) as test_client:
        yield test_client, session_factory

    app.dependency_overrides.clear()

    async def dispose():
        await engine.dispose()

    asyncio.run(dispose())
