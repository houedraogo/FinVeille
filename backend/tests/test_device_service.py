from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.device_service import DeviceService


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
    def __init__(self, devices):
        self.devices = list(devices)
        self.added = []
        self.deleted = []
        self.commits = 0

    async def execute(self, _query):
        return FakeExecuteResult(self.devices)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        return None

    async def delete(self, item):
        self.deleted.append(item)

    async def commit(self):
        self.commits += 1


def build_device(**overrides):
    now = datetime.now(timezone.utc)
    data = {
        "id": uuid4(),
        "title": "Aide test",
        "short_description": "Aide aux entreprises innovantes.",
        "full_description": None,
        "eligibility_criteria": None,
        "validation_status": "pending_review",
        "source_url": "https://example.org",
        "updated_at": now,
        "created_at": now,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_has_thin_description_detects_single_sentence():
    assert DeviceService.has_thin_description("Aide aux PME innovantes.")


def test_has_thin_description_keeps_richer_content():
    assert not DeviceService.has_thin_description(
        "Aide aux PME innovantes avec accompagnement a l'investissement. Le dispositif finance aussi les depenses de R&D.",
        None,
        None,
    )


@pytest.mark.asyncio
async def test_purge_unenrichable_devices_dry_run_returns_preview():
    thin_device = build_device()
    rich_device = build_device(
        id=uuid4(),
        short_description="Aide aux PME innovantes avec accompagnement. Le dispositif finance aussi l'amorcage industriel.",
    )
    service = DeviceService(FakeDB([thin_device, rich_device]))

    result = await service.purge_unenrichable_devices(dry_run=True)

    assert result["matched"] == 1
    assert result["deleted"] == 0
    assert result["preview"][0]["id"] == str(thin_device.id)


@pytest.mark.asyncio
async def test_purge_unenrichable_devices_deletes_matching_records():
    thin_device = build_device()
    db = FakeDB([thin_device])
    service = DeviceService(db)

    result = await service.purge_unenrichable_devices(actor_id="admin-user", dry_run=False)

    assert result["deleted"] == 1
    assert db.deleted == [thin_device]
    assert db.commits == 1
