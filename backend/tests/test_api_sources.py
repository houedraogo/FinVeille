from types import SimpleNamespace
from uuid import uuid4


def test_sources_list_endpoint_returns_sources(client, monkeypatch):
    async def fake_get_all(self, **kwargs):
        return [
            {
                "id": str(uuid4()),
                "name": "Source API",
                "organism": "Organisme",
                "country": "France",
                "region": None,
                "source_type": "portail_officiel",
                "category": "public",
                "level": 1,
                "url": "https://example.org",
                "collection_mode": "api",
                "source_kind": "listing",
                "check_frequency": "daily",
                "reliability": 5,
                "is_active": True,
                "last_checked_at": None,
                "last_success_at": None,
                "consecutive_errors": 0,
                "config": {},
                "notes": None,
                "last_error": None,
                "health_score": 92,
                "health_label": "excellent",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ]

    monkeypatch.setattr("app.services.source_service.SourceService.get_all", fake_get_all)

    response = client.get("/api/v1/sources/?category=public")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "Source API"
    assert payload[0]["health_score"] == 92


def test_sources_test_endpoint_returns_preview(client, monkeypatch):
    async def fake_test_source(self, data):
        return {
            "success": True,
            "message": "3 item(s) detecte(s).",
            "collection_mode": data.collection_mode,
            "items_found": 3,
            "sample_titles": ["Aide 1", "Aide 2"],
            "sample_urls": ["https://example.org/a1", "https://example.org/a2"],
            "can_activate": True,
        }

    monkeypatch.setattr("app.services.source_service.SourceService.test_source", fake_test_source)

    response = client.post(
        "/api/v1/sources/test",
        json={
            "url": "https://example.org/api",
            "collection_mode": "api",
            "source_kind": "listing",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["items_found"] == 3
    assert payload["can_activate"] is True


def test_sources_collect_endpoint_schedules_task(client, monkeypatch):
    source_id = str(uuid4())
    called = {"args": None}

    async def fake_get_model_by_id(self, _source_id):
        return SimpleNamespace(id=source_id, name="Source a collecter")

    class FakeCollectTask:
        @staticmethod
        def delay(arg):
            called["args"] = arg

    monkeypatch.setattr("app.services.source_service.SourceService.get_model_by_id", fake_get_model_by_id)
    monkeypatch.setattr("app.tasks.collect_tasks.collect_source", FakeCollectTask)

    response = client.post(f"/api/v1/sources/{source_id}/collect")

    assert response.status_code == 200
    assert called["args"] == source_id
    assert "Collecte planifiee" in response.json()["message"] or "Collecte planifiée" in response.json()["message"]
