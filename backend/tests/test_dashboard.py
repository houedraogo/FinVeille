from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.routers import dashboard as dashboard_router


class FakeScalarSequence:
    def __init__(self, scalar=None, items=None, one=None):
        self._scalar = scalar
        self._items = items or []
        self._one = one

    def scalar(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._one


class FakeDB:
    def __init__(self, responses):
        self._responses = list(responses)

    async def execute(self, _query):
        if not self._responses:
            raise AssertionError("Unexpected execute call")
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_dashboard_returns_error_sources(monkeypatch):
    now = datetime.now(timezone.utc)
    device = SimpleNamespace(
        id=uuid4(),
        title="Aide innovation",
        organism="Bpifrance",
        country="France",
        device_type="subvention",
        status="open",
        close_date=date.today() + timedelta(days=3),
        amount_max=Decimal("50000"),
        currency="EUR",
        confidence_score=88,
        first_seen_at=now,
    )
    source = SimpleNamespace(
        id=uuid4(),
        name="Source fragile",
        country="France",
        is_active=True,
        consecutive_errors=4,
        last_checked_at=now,
        notes=None,
        updated_at=now,
    )
    log = SimpleNamespace(started_at=now, status="failed", items_new=0, error_message="403 Forbidden")

    async def fake_get_stats(self):
        return {
            "total": 10,
            "total_active": 8,
            "new_last_7_days": 2,
            "closing_soon_30d": 1,
            "closing_soon_7d": 1,
            "pending_validation": 1,
            "avg_confidence": 82,
            "by_country": [{"country": "France", "count": 5}],
            "by_type": [{"type": "subvention", "count": 4}],
            "by_status": [{"status": "open", "count": 6}],
        }

    monkeypatch.setattr("app.routers.dashboard.DeviceService.get_stats", fake_get_stats)

    db = FakeDB([
        FakeScalarSequence(items=[device]),
        FakeScalarSequence(items=[device]),
        FakeScalarSequence(scalar=5),
        FakeScalarSequence(scalar=1),
        FakeScalarSequence(items=[source]),
        FakeScalarSequence(one=log),
        FakeScalarSequence(one=log),
    ])

    result = await dashboard_router.get_dashboard(db)

    assert result["sources"]["active"] == 5
    assert result["sources"]["in_error"] == 1
    assert result["sources"]["errors"][0]["name"] == "Source fragile"
    assert result["sources"]["errors"][0]["last_error"] == "403 Forbidden"
