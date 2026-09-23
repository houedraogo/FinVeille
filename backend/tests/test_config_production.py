"""Production must refuse insecure configuration before the app starts."""

import pytest
from pydantic import ValidationError

from app.config import Settings


SAFE_PRODUCTION = {
    "APP_ENV": "production",
    "DEBUG": False,
    "SECRET_KEY": "release-candidate-test-secret-0123456789",
    "POSTGRES_PASSWORD": "local-test-db-password",
    "DATABASE_URL": "postgresql+asyncpg://rc:local-test-db-password@postgres:5432/rc",
    "DATABASE_SYNC_URL": "postgresql://rc:local-test-db-password@postgres:5432/rc",
    "REDIS_PASSWORD": "local-test-redis-password",
    "REDIS_URL": "redis://:local-test-redis-password@redis:6379/0",
    "PUBLIC_APP_URL": "https://rc.example.test",
    "STRIPE_SECRET_KEY": None,
    "STRIPE_WEBHOOK_SECRET": None,
}


def settings(**overrides):
    return Settings(_env_file=None, **{**SAFE_PRODUCTION, **overrides})


def test_production_accepts_complete_config_with_billing_disabled():
    assert settings().APP_ENV == "production"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("SECRET_KEY", "changeme"),
        ("POSTGRES_PASSWORD", None),
        ("DATABASE_URL", "postgresql+asyncpg://rc:changeme@postgres/rc"),
        ("DATABASE_SYNC_URL", ""),
        ("REDIS_PASSWORD", None),
        ("REDIS_URL", "redis://:changeme@redis:6379/0"),
        ("DEBUG", True),
        ("PUBLIC_APP_URL", "http://localhost:3000"),
    ],
)
def test_production_rejects_insecure_critical_config(field, value):
    with pytest.raises(ValidationError, match=field):
        settings(**{field: value})


@pytest.mark.parametrize(
    "overrides",
    [
        {"STRIPE_SECRET_KEY": "sk_test_local"},
        {"STRIPE_WEBHOOK_SECRET": "whsec_local"},
        {"STRIPE_SECRET_KEY": "sk_live_replace-with-key", "STRIPE_WEBHOOK_SECRET": "whsec_local"},
        {"STRIPE_SECRET_KEY": "sk_test_local", "STRIPE_WEBHOOK_SECRET": "whsec_replace-with-key"},
    ],
)
def test_production_rejects_incomplete_or_placeholder_stripe(overrides):
    with pytest.raises(ValidationError, match="STRIPE_"):
        settings(**overrides)


def test_production_accepts_complete_test_mode_stripe():
    assert settings(STRIPE_SECRET_KEY="sk_test_local", STRIPE_WEBHOOK_SECRET="whsec_local").APP_ENV == "production"


def test_development_keeps_existing_defaults():
    assert Settings(_env_file=None, APP_ENV="development").APP_ENV == "development"
