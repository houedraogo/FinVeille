import os
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.services.match_service import find_matching_devices


POSTGRES_TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL")

pytestmark = pytest.mark.postgres_smoke

# Databases explicitly recognised as disposable test databases. Anything else is refused.
DISPOSABLE_DATABASE_PREFIXES = ("kafundo_smoke_", "kafundo_test_", "kafundo_mig_", "kafundo_lot")


@pytest.mark.skipif(not POSTGRES_TEST_URL, reason="TEST_POSTGRES_DATABASE_URL non defini")
@pytest.mark.asyncio
async def test_postgres_matching_sql_prefers_high_quality_source():
    database = make_url(POSTGRES_TEST_URL).database or ""
    assert database.startswith(DISPOSABLE_DATABASE_PREFIXES), (
        f"Refusing to run the smoke test on {database!r}: not a recognised disposable test database"
    )

    # The test builds its schema with Base.metadata.create_all and removes it afterwards. It does so in a private
    # scratch schema (search_path = that schema only), so it can never touch the tables of the database itself, and
    # cleanup is DROP SCHEMA ... CASCADE rather than Base.metadata.drop_all (which cannot order the users <->
    # organizations foreign-key cycle).
    schema = f"smoke_{uuid4().hex[:12]}"
    admin_engine = create_async_engine(POSTGRES_TEST_URL, future=True)
    engine = create_async_engine(POSTGRES_TEST_URL, future=True, connect_args={"server_settings": {"search_path": schema}})
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            await session.execute(text("DELETE FROM devices"))
            await session.execute(text("DELETE FROM sources"))

            await session.execute(
                text(
                    """
                    INSERT INTO sources (
                        id, name, organism, country, source_type, level, url, collection_mode,
                        check_frequency, reliability, category, is_active, consecutive_errors,
                        last_success_at
                    ) VALUES
                    (
                        '11111111-1111-1111-1111-111111111111',
                        'Source fiable',
                        'Org A',
                        'France',
                        'portail_officiel',
                        1,
                        'https://good.example',
                        'api',
                        'daily',
                        5,
                        'public',
                        true,
                        0,
                        NOW()
                    ),
                    (
                        '22222222-2222-2222-2222-222222222222',
                        'Source fragile',
                        'Org B',
                        'France',
                        'portail_officiel',
                        1,
                        'https://bad.example',
                        'api',
                        'daily',
                        2,
                        'public',
                        false,
                        4,
                        NOW() - INTERVAL '180 days'
                    )
                    """
                )
            )

            await session.execute(
                text(
                    """
                    INSERT INTO devices (
                        id, title, organism, country, device_type, sectors, short_description,
                        source_url, source_id, validation_status, status, close_date, search_vector,
                        last_verified_at
                    ) VALUES
                    (
                        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                        'Fonds seed fintech France',
                        'Org A',
                        'France',
                        'investissement',
                        ARRAY['finance','numerique'],
                        'Investissement seed pour startup fintech paiement',
                        'https://good.example/device',
                        '11111111-1111-1111-1111-111111111111',
                        'approved',
                        'open',
                        :close_date,
                        to_tsvector('french', 'fonds seed fintech investissement paiement france'),
                        NOW()
                    ),
                    (
                        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
                        'Fonds seed fintech France bis',
                        'Org B',
                        'France',
                        'investissement',
                        ARRAY['finance','numerique'],
                        'Investissement seed pour startup fintech paiement',
                        'https://bad.example/device',
                        '22222222-2222-2222-2222-222222222222',
                        'approved',
                        'open',
                        :close_date,
                        to_tsvector('french', 'fonds seed fintech investissement paiement france'),
                        NOW() - INTERVAL '200 days'
                    )
                    """
                ),
                {"close_date": date.today()},
            )
            await session.commit()

            profile = {
                "query": "startup fintech paiement investissement france",
                "keywords": ["fintech", "paiement", "investissement"],
                "sectors": ["finance", "numerique"],
                "countries": ["France"],
                "types": ["investissement"],
                "dominant_type": "investissement",
                "amount_min": None,
                "amount_max": None,
            }

            matches = await find_matching_devices(session, profile, limit=5)

            assert matches
            assert str(matches[0]["id"]) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    finally:
        await engine.dispose()
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin_engine.dispose()
