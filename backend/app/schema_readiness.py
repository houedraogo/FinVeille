"""Read-only PostgreSQL schema readiness check; schema changes belong to Alembic."""
from sqlalchemy import text

from app.database import engine


HEAD_REVISION = "3f8e2d1c9a05"
REQUIRED_COLUMNS = {
    ("users", "country"),
    ("users", "sectors"),
    ("users", "default_organization_id"),
    ("alerts", "organization_id"),
    ("saved_searches", "organization_id"),
    ("device_pipeline", "match_project_id"),
    ("devices", "content_sections_json"),
    ("devices", "ai_rewritten_sections_json"),
    ("devices", "ai_rewrite_status"),
    ("devices", "ai_rewrite_model"),
    ("devices", "ai_rewrite_checked_at"),
    ("devices", "ai_readiness_score"),
    ("devices", "ai_readiness_label"),
    ("devices", "ai_readiness_reasons"),
    ("user_projects", "id"),
    ("subscriptions", "last_stripe_event_created"),
    ("subscriptions", "cancel_at_period_end"),
    ("stripe_webhook_events", "id"),
    ("billing_checkouts", "organization_id"),
    ("alert_deliveries", "alert_id"),
}
REQUIRED_FOREIGN_KEYS = {
    ("users", "default_organization_id"),
    ("alerts", "organization_id"),
    ("saved_searches", "organization_id"),
    ("device_pipeline", "match_project_id"),
}


async def assert_schema_ready() -> None:
    async with engine.connect() as connection:
        version = (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
        if version != HEAD_REVISION:
            raise RuntimeError(f"Révision Alembic attendue {HEAD_REVISION}, trouvée {version}")
        columns = set((await connection.execute(text("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
        """))).all())
        missing_columns = REQUIRED_COLUMNS - columns
        if missing_columns:
            raise RuntimeError(f"Colonnes requises absentes: {sorted(missing_columns)}")
        foreign_keys = set((await connection.execute(text("""
            SELECT child.relname, attribute.attname
            FROM pg_constraint AS fk
            JOIN pg_class AS child ON child.oid = fk.conrelid
            JOIN pg_namespace AS namespace ON namespace.oid = child.relnamespace
            JOIN pg_attribute AS attribute
              ON attribute.attrelid = child.oid AND attribute.attnum = ANY(fk.conkey)
            WHERE namespace.nspname = 'public' AND fk.contype = 'f'
        """))).all())
        missing_foreign_keys = REQUIRED_FOREIGN_KEYS - foreign_keys
        if missing_foreign_keys:
            raise RuntimeError(f"Clés étrangères requises absentes: {sorted(missing_foreign_keys)}")
