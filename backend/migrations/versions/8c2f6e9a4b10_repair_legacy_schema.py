"""Safely reconcile a verified legacy schema and install PostgreSQL triggers.

Revision ID: 8c2f6e9a4b10
Revises: 5a37a54cae56
"""
import json

from alembic import op
import sqlalchemy as sa

from migrations.schema_contract import apply_additions, inspect_legacy


revision = "8c2f6e9a4b10"
down_revision = "5a37a54cae56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    plan = inspect_legacy(connection)  # Checks types, nullability, orphans and duplicates before DDL.
    apply_additions(connection, plan)
    remaining = inspect_legacy(connection)
    if any(remaining.values()):
        raise RuntimeError(f"Réparation du schéma incomplète: {remaining}")

    connection.execute(sa.text("""
        CREATE OR REPLACE FUNCTION devices_search_vector_update()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.search_vector :=
            setweight(to_tsvector('french', coalesce(NEW.title, '')), 'A') ||
            setweight(to_tsvector('french', coalesce(NEW.organism, '')), 'B') ||
            setweight(to_tsvector('french', coalesce(NEW.short_description, '')), 'B') ||
            setweight(to_tsvector('french', coalesce(NEW.full_description, '')), 'C') ||
            setweight(to_tsvector('french', coalesce(NEW.country, '')), 'C') ||
            setweight(to_tsvector('french', coalesce(NEW.region, '')), 'D') ||
            setweight(to_tsvector('french', coalesce(NEW.zone, '')), 'D') ||
            setweight(to_tsvector('french', coalesce(array_to_string(NEW.sectors, ' '), '')), 'B') ||
            setweight(to_tsvector('french', coalesce(array_to_string(NEW.keywords, ' '), '')), 'C') ||
            setweight(to_tsvector('french', coalesce(array_to_string(NEW.tags, ' '), '')), 'D') ||
            setweight(to_tsvector('french', coalesce(NEW.auto_summary, '')), 'D');
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """))
    connection.execute(sa.text("DROP TRIGGER IF EXISTS tsvector_devices_update ON devices"))
    connection.execute(sa.text("""
        CREATE TRIGGER tsvector_devices_update
        BEFORE INSERT OR UPDATE OF title, organism, short_description, full_description,
          country, region, zone, sectors, keywords, tags, auto_summary
        ON devices FOR EACH ROW EXECUTE FUNCTION devices_search_vector_update()
    """))

    connection.execute(sa.text("""
        CREATE OR REPLACE FUNCTION devices_auto_expire()
        RETURNS TRIGGER AS $$
        BEGIN
          IF NEW.close_date IS NOT NULL AND NEW.close_date < CURRENT_DATE AND NEW.status = 'open' THEN
            NEW.status := 'expired';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """))
    connection.execute(sa.text("DROP TRIGGER IF EXISTS auto_expire_devices ON devices"))
    connection.execute(sa.text("""
        CREATE TRIGGER auto_expire_devices
        BEFORE INSERT OR UPDATE OF close_date, status
        ON devices FOR EACH ROW EXECUTE FUNCTION devices_auto_expire()
    """))

    # The old startup path initialized plans. Preserve existing plan rows and
    # supply the free tier required by signup and billing-context reads.
    connection.execute(sa.text("""
        INSERT INTO plans (
          id, slug, name, description, price_monthly_eur, currency,
          limits, features, sort_order, is_active
        ) VALUES (
          gen_random_uuid(), 'free', 'Decouverte',
          'Accès de découverte aux opportunités et à la veille.', 0, 'EUR',
          CAST(:limits_json AS json), CAST(:features_json AS json),
          1, true
        ) ON CONFLICT (slug) DO NOTHING
    """), {
        "limits_json": json.dumps({"users": 1, "alerts": 3, "saved_searches": 5, "pipeline_projects": 15}),
        "features_json": json.dumps({
            "matching_ai": False, "smart_scoring": False, "custom_alerts": False,
            "collaboration": False, "advanced_analysis": False, "exports": False,
            "api_access": False, "strategic_watch": False, "private_sources": False,
            "funding_support": False,
        }),
    })


def downgrade() -> None:
    raise RuntimeError("Downgrade interdit: revenir à un schéma incomplet compromettrait les données Kafundo")
