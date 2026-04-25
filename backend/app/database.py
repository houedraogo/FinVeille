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
    await ensure_saas_columns()
    await ensure_workspace_columns()
    await ensure_billing_columns()
    await ensure_billing_defaults()
    await ensure_device_content_columns()
    await ensure_pipeline_documents_column()
    await ensure_device_decision_columns()
    await ensure_search_vector_trigger()


async def ensure_saas_columns():
    """Ajoute les colonnes SaaS sur les bases locales déjà existantes."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS platform_role VARCHAR(50) NOT NULL DEFAULT 'member'
        """))
        await conn.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS default_organization_id UUID NULL
        """))
        await conn.execute(text("""
            ALTER TABLE alerts
            ADD COLUMN IF NOT EXISTS organization_id UUID NULL
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_alerts_organization_id
            ON alerts (organization_id)
        """))


async def ensure_workspace_columns():
    """Ajoute les colonnes workspace sur les bases locales deja existantes."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE saved_searches
            ADD COLUMN IF NOT EXISTS organization_id UUID NULL
        """))
        await conn.execute(text("""
            ALTER TABLE saved_searches
            ADD COLUMN IF NOT EXISTS title VARCHAR(255) NULL
        """))
        await conn.execute(text("""
            ALTER TABLE saved_searches
            ADD COLUMN IF NOT EXISTS path VARCHAR(255) NULL
        """))
        await conn.execute(text("""
            ALTER TABLE saved_searches
            ADD COLUMN IF NOT EXISTS result_count INTEGER NULL
        """))
        await conn.execute(text("""
            ALTER TABLE saved_searches
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NULL DEFAULT now()
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_saved_searches_organization_id
            ON saved_searches (organization_id)
        """))
        await conn.execute(text("""
            ALTER TABLE device_pipeline
            ADD COLUMN IF NOT EXISTS priority VARCHAR(20) NOT NULL DEFAULT 'moyenne'
        """))
        await conn.execute(text("""
            ALTER TABLE device_pipeline
            ADD COLUMN IF NOT EXISTS reminder_date DATE NULL
        """))
        await conn.execute(text("""
            ALTER TABLE device_pipeline
            ADD COLUMN IF NOT EXISTS match_project_id UUID NULL
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_device_pipeline_match_project_id
            ON device_pipeline (match_project_id)
        """))


async def ensure_billing_columns():
    """Aligne les anciennes bases locales sur le schema billing actuel."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'plans'
                  AND column_name = 'is_active'
                  AND data_type <> 'boolean'
              ) THEN
                ALTER TABLE plans
                ALTER COLUMN is_active TYPE BOOLEAN
                USING CASE
                  WHEN lower(is_active::text) IN ('true', 't', '1', 'yes', 'on') THEN TRUE
                  ELSE FALSE
                END;
              END IF;
            END $$;
        """))
        await conn.execute(text("""
            UPDATE plans
            SET is_active = TRUE
            WHERE is_active IS NULL
        """))
        await conn.execute(text("""
            ALTER TABLE plans
            ALTER COLUMN is_active SET DEFAULT TRUE
        """))
        await conn.execute(text("""
            ALTER TABLE plans
            ALTER COLUMN is_active SET NOT NULL
        """))


async def ensure_billing_defaults():
    """Initialise les plans SaaS par defaut."""
    from app.services.billing_service import ensure_default_plans

    async with AsyncSessionLocal() as session:
        await ensure_default_plans(session)


async def ensure_device_content_columns():
    """Ajoute les colonnes de contenu structure pour les bases locales existantes."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE devices
            ADD COLUMN IF NOT EXISTS content_sections_json JSON NULL
        """))
        await conn.execute(text("""
            ALTER TABLE devices
            ADD COLUMN IF NOT EXISTS ai_rewritten_sections_json JSON NULL
        """))
        await conn.execute(text("""
            ALTER TABLE devices
            ADD COLUMN IF NOT EXISTS ai_rewrite_status VARCHAR(50) NOT NULL DEFAULT 'pending'
        """))
        await conn.execute(text("""
            ALTER TABLE devices
            ADD COLUMN IF NOT EXISTS ai_rewrite_model VARCHAR(120) NULL
        """))
        await conn.execute(text("""
            ALTER TABLE devices
            ADD COLUMN IF NOT EXISTS ai_rewrite_checked_at TIMESTAMPTZ NULL
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_devices_ai_rewrite_status
            ON devices (ai_rewrite_status)
        """))
        await conn.execute(text("""
            ALTER TABLE devices
            ADD COLUMN IF NOT EXISTS ai_readiness_score SMALLINT NOT NULL DEFAULT 0
        """))
        await conn.execute(text("""
            ALTER TABLE devices
            ADD COLUMN IF NOT EXISTS ai_readiness_label VARCHAR(80) NULL
        """))
        await conn.execute(text("""
            ALTER TABLE devices
            ADD COLUMN IF NOT EXISTS ai_readiness_reasons TEXT[] NULL
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_devices_ai_readiness_label
            ON devices (ai_readiness_label)
        """))


async def ensure_pipeline_documents_column():
    """Ajoute la colonne documents sur device_pipeline pour les bases existantes."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE device_pipeline
            ADD COLUMN IF NOT EXISTS documents JSON NULL
        """))


async def ensure_device_decision_columns():
    """Ajoute les colonnes d'analyse décisionnelle IA sur les bases existantes."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE devices
            ADD COLUMN IF NOT EXISTS decision_analysis JSON NULL
        """))
        await conn.execute(text("""
            ALTER TABLE devices
            ADD COLUMN IF NOT EXISTS decision_analyzed_at TIMESTAMPTZ NULL
        """))


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
