import pytest
from fastapi import HTTPException

from app.config import settings
from app.utils.google_auth import verify_google_credential


class MockResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class MockAsyncClient:
    def __init__(self, response: MockResponse):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *_args, **_kwargs):
        return self.response


@pytest.mark.asyncio
async def test_verify_google_credential_accepts_verified_email(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setattr(
        "app.utils.google_auth.httpx.AsyncClient",
        lambda **_kwargs: MockAsyncClient(
            MockResponse(
                200,
                {
                    "aud": "google-client-id",
                    "email": "user@example.com",
                    "email_verified": "true",
                    "name": "Jane Doe",
                },
            )
        ),
    )

    payload = await verify_google_credential("credential")

    assert payload["email"] == "user@example.com"
    assert payload["full_name"] == "Jane Doe"


@pytest.mark.asyncio
async def test_verify_google_credential_rejects_wrong_audience(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setattr(
        "app.utils.google_auth.httpx.AsyncClient",
        lambda **_kwargs: MockAsyncClient(
            MockResponse(
                200,
                {
                    "aud": "another-client-id",
                    "email": "user@example.com",
                    "email_verified": "true",
                },
            )
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await verify_google_credential("credential")

    assert exc.value.status_code == 401
    assert "autorisé" in exc.value.detail
