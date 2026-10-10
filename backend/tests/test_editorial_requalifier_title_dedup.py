"""Root cause: `requalify_editorial_auto_sources` ran every 2h on the same device for up to 21 days.
Its selection query had no guard against reprocessing a device it had already requalified, and
`_fallback_title` prepended a new type prefix onto `device.title` without stripping the one a previous
run had already added - stacking "Subvention - Subvention - Subvention - ..." a little more each run.

Fix: `_fallback_title` strips every known prefix before adding its own (idempotent on an already-prefixed
title), and the selection query excludes devices this module already requalified (ai_rewrite_model).
"""
import json
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.dialects.postgresql import ARRAY as PGArray
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.device import Device
from app.models.source import Source
from app.services.editorial_requalifier import _fallback_title, _strip_known_title_prefixes

# The sqlite compiler shim in conftest.py fixes the DDL (ARRAY -> TEXT) but not parameter binding:
# sqlite3 can't bind a Python list. Patch bind/result processing for sqlite only; untouched elsewhere.
_orig_array_bind = PGArray.bind_processor
_orig_array_result = PGArray.result_processor


def _sqlite_array_bind_processor(self, dialect):
    if dialect.name != "sqlite":
        return _orig_array_bind(self, dialect)
    return lambda value: None if value is None else json.dumps(value)


def _sqlite_array_result_processor(self, dialect, coltype):
    if dialect.name != "sqlite":
        return _orig_array_result(self, dialect, coltype)
    return lambda value: None if value is None else json.loads(value)


PGArray.bind_processor = _sqlite_array_bind_processor
PGArray.result_processor = _sqlite_array_result_processor

# tests/conftest.py registers the sqlite compiler shims for UUID/ARRAY/TSVECTOR on import,
# which pytest guarantees happens before this module's tests run.


class TestStripKnownTitlePrefixes:
    @pytest.mark.parametrize("title,expected", [
        ("Subvention - Subvention - Subvention - OpenAI Grant Program 2026", "OpenAI Grant Program 2026"),
        ("Concours - Concours - Concours - Concours - D-Prize Challenge", "D-Prize Challenge"),
        ("Subvention - OpenAI Grant Program 2026", "OpenAI Grant Program 2026"),
        ("OpenAI Grant Program 2026", "OpenAI Grant Program 2026"),
        ("Appel à projets - Appel a projets - Horizon Europe", "Horizon Europe"),
        ("", ""),
    ])
    def test_strips_every_repetition(self, title, expected):
        assert _strip_known_title_prefixes(title) == expected


class TestFallbackTitleIsIdempotent:
    """Re-running _fallback_title on its own previous output must never stack a prefix."""

    @pytest.mark.parametrize("device_type", ["subvention", "concours", "aap", "ami", "accompagnement", "investissement"])
    def test_running_twice_gives_the_same_result_as_running_once(self, device_type):
        once = _fallback_title("OpenAI's AI & Teen Development Research Grant Program 2026", device_type)
        twice = _fallback_title(once, device_type)
        assert once == twice
        assert once.count(" - ") == 1  # exactly one "Type - " prefix, never stacked

    def test_running_many_times_never_stacks(self):
        title = "Call for Applications: California Documentary Project Grants 2026/2027"
        for _ in range(10):
            title = _fallback_title(title, "subvention")
        assert title.count("Subvention - Subvention") == 0
        assert title.startswith("Subvention - California Documentary Project Grants")

    def test_already_stacked_title_is_collapsed_back_to_one_prefix(self):
        stacked = "Subvention - Subvention - Subvention - Subvention - Subvention - Grant 2026"
        fixed = _fallback_title(stacked, "subvention")
        assert fixed == "Subvention - Grant 2026"


@pytest.fixture
async def sqlite_session_factory(tmp_path):
    db_path = tmp_path / f"test-{uuid4().hex}.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def _editorial_source(**overrides) -> Source:
    base = dict(
        id=uuid4(), name="Opportunity Desk", organism="Opportunity Desk", country="International",
        source_type="autre", level=3, url="https://opportunitydesk.org/feed/", collection_mode="rss",
        reliability=3, category="public", is_active=True, config={"source_kind": "editorial_opportunities"},
    )
    base.update(overrides)
    return Source(**base)


def _device(*, source_id, **overrides) -> Device:
    base = dict(
        id=uuid4(), title="AGNES Intra-Africa Mobility Grants for Junior Researchers 2026", organism="Opportunity Desk",
        country="International", device_type="subvention", source_id=source_id,
        source_url="https://opportunitydesk.org/x", source_raw="Grant for entrepreneurs and startups. Apply now.",
        status="open", close_date=date.today() + timedelta(days=60), validation_status="admin_only",
    )
    base.update(overrides)
    return Device(**base)


def _has_stacked_prefix(title: str) -> bool:
    """True if the title starts with the same '<word(s)> - ' segment twice in a row."""
    parts = title.split(" - ")
    return len(parts) >= 2 and parts[0] == parts[1] and parts[0] != ""


class TestRequalifierDoesNotReprocessItsOwnOutput:
    async def test_device_requalified_once_is_excluded_from_the_next_selection(self, sqlite_session_factory, monkeypatch):
        """A device this module already requalified must not be selected again on the next scheduled run."""
        import app.services.editorial_requalifier as mod

        monkeypatch.setattr(mod, "AsyncSessionLocal", sqlite_session_factory)

        async with sqlite_session_factory() as db:
            source = _editorial_source()
            db.add(source)
            await db.flush()
            device = _device(source_id=source.id)
            db.add(device)
            await db.commit()
            device_id = device.id

        await mod.requalify_editorial_auto_sources(batch_size=80)
        async with sqlite_session_factory() as db:
            refreshed = await db.get(Device, device_id)
            title_after_first_run = refreshed.title
            checked_at_after_first_run = refreshed.ai_rewrite_checked_at
            assert refreshed.ai_rewrite_model == "editorial_requalifier_v1"
            assert not _has_stacked_prefix(title_after_first_run)

        # A second scheduled run (2h later in production) must not re-select this device at all:
        # ai_rewrite_checked_at (set fresh to "now" on every pass that selects a device) must be untouched.
        await mod.requalify_editorial_auto_sources(batch_size=80)
        async with sqlite_session_factory() as db:
            refreshed = await db.get(Device, device_id)
            assert refreshed.title == title_after_first_run
            assert refreshed.ai_rewrite_checked_at == checked_at_after_first_run

    async def test_many_scheduled_runs_never_stack_the_prefix(self, sqlite_session_factory, monkeypatch):
        """Regression guard for the exact production bug: simulate the 2h-cadence beat task running repeatedly."""
        import app.services.editorial_requalifier as mod

        monkeypatch.setattr(mod, "AsyncSessionLocal", sqlite_session_factory)

        async with sqlite_session_factory() as db:
            source = _editorial_source()
            db.add(source)
            await db.flush()
            device = _device(source_id=source.id, title="OpenAI's AI & Teen Development Research Grant Program 2026")
            db.add(device)
            await db.commit()
            device_id = device.id

        for _ in range(8):
            await mod.requalify_editorial_auto_sources(batch_size=80)

        async with sqlite_session_factory() as db:
            refreshed = await db.get(Device, device_id)
            assert not _has_stacked_prefix(refreshed.title)
            assert refreshed.title.startswith("Subvention - OpenAI")
