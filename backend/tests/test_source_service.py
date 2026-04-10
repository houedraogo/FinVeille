from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.source import SourceCreate
from app.services.source_service import SourceService


class FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return FakeScalarResult(self._items)


class FakeDB:
    def __init__(self, logs):
        self.logs = logs

    async def execute(self, _query):
        return FakeExecuteResult(self.logs)


def build_source(**overrides):
    now = datetime.now(timezone.utc)
    data = {
        "id": uuid4(),
        "name": "Source test",
        "organism": "Organisme",
        "country": "France",
        "region": None,
        "source_type": "portail_officiel",
        "category": "public",
        "level": 1,
        "url": "https://example.org",
        "collection_mode": "api",
        "check_frequency": "daily",
        "reliability": 5,
        "is_active": True,
        "last_checked_at": now,
        "last_success_at": now - timedelta(days=1),
        "consecutive_errors": 0,
        "config": {},
        "notes": None,
        "created_at": now - timedelta(days=90),
        "updated_at": now,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def build_log(source_id, **overrides):
    now = datetime.now(timezone.utc)
    data = {
        "source_id": source_id,
        "started_at": now - timedelta(days=1),
        "status": "success",
        "items_found": 12,
        "items_new": 4,
        "items_updated": 3,
        "items_skipped": 5,
        "items_error": 0,
        "error_message": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_compute_health_rewards_recent_reliable_sources():
    service = SourceService(db=None)
    source = build_source()
    logs = [build_log(source.id), build_log(source.id, started_at=datetime.now(timezone.utc) - timedelta(days=5))]

    score, label = service._compute_health(source, logs)

    assert score >= 85
    assert label == "excellent"


def test_compute_health_penalizes_error_prone_stale_sources():
    service = SourceService(db=None)
    source = build_source(
        reliability=2,
        is_active=False,
        consecutive_errors=4,
        last_success_at=datetime.now(timezone.utc) - timedelta(days=200),
    )
    logs = [build_log(source.id, status="failed", items_found=0, items_new=0, items_updated=0, error_message="403")]

    score, label = service._compute_health(source, logs)

    assert score < 50
    assert label == "critique"


async def test_serialize_sources_includes_last_error_and_health():
    source = build_source(consecutive_errors=2, notes="note source")
    logs = [
        build_log(source.id, status="failed", error_message="Timeout distant"),
        build_log(source.id, status="success", error_message=None),
    ]
    service = SourceService(db=FakeDB(logs))

    payload = await service._serialize_sources_with_last_error([source])

    assert len(payload) == 1
    assert payload[0]["last_error"] == "Timeout distant"
    assert 0 <= payload[0]["health_score"] <= 100
    assert payload[0]["health_label"] in {"excellent", "bon", "fragile", "critique"}


def test_prepare_source_payload_sets_single_program_defaults():
    service = SourceService(db=None)

    prepared = service._prepare_source_payload({
        "name": "ABH",
        "organism": "ABH",
        "country": "International",
        "region": None,
        "source_type": "portail_officiel",
        "category": "private",
        "level": 2,
        "url": "https://example.org/programme-2026",
        "collection_mode": "html",
        "source_kind": "single_program_page",
        "check_frequency": "daily",
        "reliability": 3,
        "is_active": True,
        "config": {},
        "notes": None,
    })

    assert prepared["config"]["source_kind"] == "single_program_page"
    assert prepared["config"]["list_selector"] == "body"
    assert prepared["config"]["item_title_selector"] == "h1"
    assert prepared["config"]["detail_fetch"] is False


def test_prepare_source_payload_marks_pdf_manual_in_config():
    service = SourceService(db=None)

    prepared = service._prepare_source_payload({
        "name": "Prix PDF",
        "organism": "Fondation",
        "country": "France",
        "region": None,
        "source_type": "portail_officiel",
        "category": "private",
        "level": 2,
        "url": "https://example.org/reglement.pdf",
        "collection_mode": "manual",
        "source_kind": "pdf_manual",
        "check_frequency": "daily",
        "reliability": 3,
        "is_active": True,
        "config": {},
        "notes": None,
    })

    assert prepared["config"]["source_kind"] == "pdf_manual"
    assert prepared["config"]["document_type"] == "pdf"


def test_source_create_rejects_homepage_listing_without_minimal_config():
    with pytest.raises(ValueError):
        SourceCreate(
            name="Home",
            organism="Org",
            country="France",
            source_type="portail_officiel",
            category="public",
            level=2,
            url="https://example.org/",
            collection_mode="html",
            source_kind="listing",
            config={},
        )


def test_source_create_allows_homepage_single_program_page_without_config():
    source = SourceCreate(
        name="Programme unique",
        organism="Org",
        country="France",
        source_type="portail_officiel",
        category="public",
        level=2,
        url="https://example.org/",
        collection_mode="html",
        source_kind="single_program_page",
        config={},
    )

    assert source.source_kind == "single_program_page"
