def test_match_rejects_unsupported_extension(client):
    response = client.post(
        "/api/v1/match/",
        files={"file": ("pitch.docx", b"fake-content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 422
    assert "Format" in response.json()["detail"]


def test_match_rejects_oversized_file(client):
    big_content = b"x" * (10 * 1024 * 1024 + 1)
    response = client.post(
        "/api/v1/match/",
        files={"file": ("pitch.txt", big_content, "text/plain")},
    )

    assert response.status_code == 422
    assert "volumineux" in response.json()["detail"]


def test_match_returns_matches(client, monkeypatch):
    async def fake_match_project(db, filename, content, limit=15):
        return {
            "profile": {
                "sectors": ["finance"],
                "countries": ["France"],
                "types": ["investissement"],
                "dominant_type": "investissement",
                "summary": "Startup fintech",
                "keywords": ["fintech", "paiement"],
            },
            "matches": [
                {
                    "id": "device-1",
                    "title": "Fonds seed fintech",
                    "match_score": 87,
                }
            ],
        }

    monkeypatch.setattr("app.routers.match.match_project", fake_match_project)

    response = client.post(
        "/api/v1/match/?limit=5",
        files={"file": ("pitch.txt", b"startup fintech de paiement", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["dominant_type"] == "investissement"
    assert payload["matches"][0]["match_score"] == 87
