from pydantic_settings import BaseSettings
from typing import Optional


from pydantic import model_validator


INSECURE_SECRET_MARKERS = (
    "changeme",
    "change-me",
    "replace-with",
    "dev-secret",
    "not-for-production",
)


def _contains_insecure_marker(value: str | None) -> bool:
    lowered = str(value or "").lower()
    return any(marker in lowered for marker in INSECURE_SECRET_MARKERS)


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Kafundo"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Sécurité
    SECRET_KEY: str = "changeme-dev-secret-key-not-for-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 heures

    # Base de données
    POSTGRES_PASSWORD: Optional[str] = None
    DATABASE_URL: str = "postgresql+asyncpg://kafundo:changeme@localhost:5432/kafundo"
    DATABASE_SYNC_URL: str = "postgresql://kafundo:changeme@localhost:5432/kafundo"

    # Redis / Celery
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: str = "redis://:changeme@redis:6379/0"

    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "noreply@kafundo.com"
    ADMIN_EMAIL: str = "contact@kafundo.com"

    # Collecte
    DEFAULT_REQUEST_TIMEOUT: int = 30
    DEFAULT_REQUEST_DELAY: float = 1.5
    MAX_RETRIES: int = 3
    AUTO_PUBLISH_MIN_CONFIDENCE: int = 55

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None

    # Billing / Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICE_PRO: Optional[str] = None
    STRIPE_PRICE_TEAM: Optional[str] = None
    STRIPE_PRICE_EXPERT: Optional[str] = None
    STRIPE_PRICE_ENTERPRISE: Optional[str] = None
    STRIPE_CHECKOUT_SUCCESS_URL: str = "http://localhost:3000/billing?checkout=success"
    STRIPE_CHECKOUT_CANCEL_URL: str = "http://localhost:3000/billing?checkout=cancel"
    STRIPE_PORTAL_RETURN_URL: str = "http://localhost:3000/billing"

    # Production / observabilite
    APP_ENV: str = "development"
    SENTRY_DSN: Optional[str] = None
    PUBLIC_APP_URL: str = "http://localhost:3000"
    BACKUP_RETENTION_DAYS: int = 14

    # LLM
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None
    AI_REWRITE_PROVIDER: str = "openai"
    AI_REWRITE_MODEL: str = "gpt-4o-mini"
    AI_MATCH_MODEL: str = "gpt-4.1"
    AI_REWRITE_TIMEOUT_SECONDS: int = 45
    AI_MATCH_TIMEOUT_SECONDS: int = 60

    # CORS
    FRONTEND_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000"

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None

    # Sources tierces
    LES_AIDES_API_IDC: Optional[str] = None
    AIDES_ENTREPRISES_API_ID: Optional[str] = None
    AIDES_ENTREPRISES_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "ignore"

    @model_validator(mode="after")
    def validate_production_secrets(self):
        import logging
        env = (self.APP_ENV or "").lower()
        if env not in {"production", "prod"}:
            return self

        warnings: list[str] = []
        if _contains_insecure_marker(self.SECRET_KEY) or len(self.SECRET_KEY or "") < 32:
            warnings.append("SECRET_KEY doit etre une valeur aleatoire forte en production.")

        for field_name in (
            "POSTGRES_PASSWORD",
            "DATABASE_URL",
            "DATABASE_SYNC_URL",
            "REDIS_PASSWORD",
            "REDIS_URL",
        ):
            if _contains_insecure_marker(getattr(self, field_name, None)):
                warnings.append(f"{field_name} contient encore une valeur par defaut ou placeholder.")

        if self.DEBUG:
            warnings.append("DEBUG doit etre false en production.")
        if "localhost" in (self.PUBLIC_APP_URL or ""):
            warnings.append("PUBLIC_APP_URL ne doit pas pointer vers localhost en production.")
        if self.STRIPE_SECRET_KEY and _contains_insecure_marker(self.STRIPE_SECRET_KEY):
            warnings.append("STRIPE_SECRET_KEY contient encore une valeur placeholder.")

        if warnings:
            logging.getLogger(__name__).warning(
                "[Config] Avertissements production: %s", " | ".join(warnings)
            )
        return self


settings = Settings()
