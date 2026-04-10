import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _fresh_db():
    """Cree un engine/session frais a chaque appel pour eviter les conflits d'event loop."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import settings

    engine = create_async_engine(settings.DATABASE_URL, pool_size=3, max_overflow=5)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300, queue="collect")
def collect_source(self, source_id: str):
    """Collecte une source specifique."""
    try:
        asyncio.run(_collect_source_async(source_id))
    except Exception as exc:
        logger.error(f"[Task] Erreur collecte source {source_id}: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(queue="collect")
def collect_by_level(level: int):
    """Declenche la collecte de toutes les sources actives d'un niveau."""
    asyncio.run(_collect_by_level_async(level))


@celery_app.task(queue="collect")
def collect_all_active():
    """Declenche la collecte de toutes les sources actives."""
    for level in [1, 2, 3]:
        asyncio.run(_collect_by_level_async(level))


async def _collect_by_level_async(level: int):
    from sqlalchemy import select
    from app.models.source import Source

    async with _fresh_db() as db:
        result = await db.execute(select(Source).where(Source.level == level, Source.is_active == True))
        sources = result.scalars().all()

    logger.info(f"[Scheduler] Niveau {level} : {len(sources)} sources a collecter")
    for source in sources:
        collect_source.apply_async(args=[str(source.id)], queue="collect")


async def _collect_source_async(source_id: str):
    from sqlalchemy import select
    from sqlalchemy.sql import func
    from app.collector.api_connector import APIConnector
    from app.collector.html_connector import HTMLConnector
    from app.collector.les_aides_connector import LesAidesConnector
    from app.collector.pipeline import CollectionPipeline
    from app.collector.rss_connector import RSSConnector
    from app.models.collection_log import CollectionLog
    from app.models.source import Source

    connectors = {
        "rss": RSSConnector,
        "atom": RSSConnector,
        "api": APIConnector,
        "html": HTMLConnector,
        "les_aides": LesAidesConnector,
    }

    async with _fresh_db() as db:
        result = await db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()

        if not source or not source.is_active:
            logger.warning(f"[Task] Source {source_id} introuvable ou inactive")
            return

        source_dict = {
            "id": str(source.id),
            "name": source.name,
            "organism": source.organism,
            "country": source.country,
            "collection_mode": source.collection_mode,
            "url": source.url,
            "level": source.level,
            "config": source.config or {},
            "language": "fr",
        }

        if source.collection_mode == "manual":
            logger.info(f"[Task] Source '{source.name}' en mode manuel, collecte auto ignoree")
            source.last_checked_at = func.now()
            await db.commit()
            return

        connector_class = connectors.get(source.collection_mode)
        if not connector_class:
            logger.warning(f"[Task] Mode non supporte : {source.collection_mode}")
            source.consecutive_errors = (source.consecutive_errors or 0) + 1
            source.last_checked_at = func.now()
            db.add(CollectionLog(
                source_id=source.id,
                status="failed",
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                error_message=f"Mode de collecte non supporte: {source.collection_mode}",
            ))
            await db.commit()
            return

        connector = connector_class(source_dict)
        collection_result = await connector.collect()

        if collection_result.success:
            pipeline = CollectionPipeline(db, source_dict)
            await pipeline.process(collection_result)
            source.consecutive_errors = 0
            source.last_success_at = func.now()
            logger.info(f"[Task] Source '{source.name}' collectee avec succes")
        else:
            source.consecutive_errors = (source.consecutive_errors or 0) + 1
            db.add(CollectionLog(
                source_id=source.id,
                status="failed",
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                error_message=collection_result.error,
            ))
            if source.consecutive_errors >= 5:
                source.is_active = False
                logger.error(f"[Task] Source '{source.name}' desactivee apres 5 erreurs")
            logger.warning(f"[Task] Echec collecte '{source.name}': {collection_result.error}")

        source.last_checked_at = func.now()
        await db.commit()
