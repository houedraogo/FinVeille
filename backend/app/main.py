from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import create_tables
from app.routers import auth, devices, sources, alerts, dashboard, admin, match, organizations, workspace, billing, security, relevance

if settings.SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.APP_ENV,
            traces_sample_rate=0.1,
        )
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — crée les tables si elles n'existent pas, puis installe les triggers
    await create_tables()
    yield
    # Shutdown (nettoyage si besoin)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Plateforme de veille sur les dispositifs de financement public — France & Afrique",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(sources.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(match.router)
app.include_router(organizations.router)
app.include_router(workspace.router)
app.include_router(billing.router)
app.include_router(security.router)
app.include_router(relevance.router)


@app.get("/api/health", tags=["health"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/api/health/detailed", tags=["health"])
async def health_detailed():
    from app.database import engine
    from sqlalchemy import text
    checks = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    try:
        import redis
        import os
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    return checks
