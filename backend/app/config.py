from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "FinVeille"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Sécurité
    SECRET_KEY: str = "changeme-dev-secret-key-not-for-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 heures

    # Base de données
    DATABASE_URL: str = "postgresql+asyncpg://finveille:changeme@localhost:5432/finveille"
    DATABASE_SYNC_URL: str = "postgresql://finveille:changeme@localhost:5432/finveille"

    # Redis / Celery
    REDIS_URL: str = "redis://:changeme@redis:6379/0"

    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "noreply@finveille.com"

    # Collecte
    DEFAULT_REQUEST_TIMEOUT: int = 30
    DEFAULT_REQUEST_DELAY: float = 1.5
    MAX_RETRIES: int = 3
    AUTO_PUBLISH_MIN_CONFIDENCE: int = 55

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None

    # LLM
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None

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


settings = Settings()
