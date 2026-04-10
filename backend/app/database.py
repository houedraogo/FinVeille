from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Crée toutes les tables (développement uniquement — utiliser Alembic en prod)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_search_vector_trigger()


async def ensure_search_vector_trigger():
    """
    Crée (ou recrée) le trigger PostgreSQL qui maintient search_vector
    automatiquement sur INSERT et UPDATE des colonnes texte de devices.
    Idempotent — peut être appelé à chaque démarrage.
    """
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION devices_search_vector_update()
            RETURNS TRIGGER AS $$
            BEGIN
              NEW.search_vector :=
                setweight(to_tsvector('french', coalesce(NEW.title, '')),             'A') ||
                setweight(to_tsvector('french', coalesce(NEW.organism, '')),          'B') ||
                setweight(to_tsvector('french', coalesce(NEW.short_description, '')), 'B') ||
                setweight(to_tsvector('french', coalesce(NEW.full_description, '')),  'C') ||
                setweight(to_tsvector('french', coalesce(NEW.country, '')),           'C') ||
                setweight(to_tsvector('french', coalesce(NEW.region, '')),            'D') ||
                setweight(to_tsvector('french', coalesce(NEW.zone, '')),              'D') ||
                setweight(to_tsvector('french',
                    coalesce(array_to_string(NEW.sectors,  ' '), '')),                'B') ||
                setweight(to_tsvector('french',
                    coalesce(array_to_string(NEW.keywords, ' '), '')),                'C') ||
                setweight(to_tsvector('french',
                    coalesce(array_to_string(NEW.tags,     ' '), '')),                'D') ||
                setweight(to_tsvector('french', coalesce(NEW.auto_summary, '')),      'D');
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))

        await conn.execute(text(
            "DROP TRIGGER IF EXISTS tsvector_devices_update ON devices"
        ))
        await conn.execute(text("""
            CREATE TRIGGER tsvector_devices_update
              BEFORE INSERT OR UPDATE OF
                title, organism, short_description, full_description,
                country, region, zone, sectors, keywords, tags, auto_summary
              ON devices
              FOR EACH ROW EXECUTE FUNCTION devices_search_vector_update()
        """))

        # ── Trigger 2 : auto-expire les dispositifs dont la date est dépassée ──
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION devices_auto_expire()
            RETURNS TRIGGER AS $$
            BEGIN
              IF NEW.close_date IS NOT NULL
                 AND NEW.close_date < CURRENT_DATE
                 AND NEW.status = 'open' THEN
                NEW.status := 'expired';
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))
        await conn.execute(text(
            "DROP TRIGGER IF EXISTS auto_expire_devices ON devices"
        ))
        await conn.execute(text("""
            CREATE TRIGGER auto_expire_devices
              BEFORE INSERT OR UPDATE OF close_date, status
              ON devices
              FOR EACH ROW EXECUTE FUNCTION devices_auto_expire()
        """))
