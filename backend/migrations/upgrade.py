"""Guarded Alembic upgrade for deployment.

An empty database upgrades directly. An existing database requires a verified
backup; an unversioned historical database additionally needs baseline_legacy.
"""
import argparse

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import settings
from migrations.schema_contract import inspect_legacy


HEAD_REVISION = "f54e3b706d18"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-confirmed", action="store_true")
    args = parser.parse_args()
    engine = create_engine(settings.DATABASE_SYNC_URL)
    try:
        with engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(42978122)"))
            tables = set(inspect(connection).get_table_names(schema="public"))
            business_tables = tables - {"alembic_version"}
            versions = (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
                if "alembic_version" in tables else []
            )
            if versions == [HEAD_REVISION]:
                inspect_legacy(connection, allow_post_baseline_tables=True)
                print(f"Schéma déjà à head: {HEAD_REVISION}")
                return
            if business_tables and not versions:
                raise RuntimeError(
                    "Base historique non versionnée: sauvegarder, contrôler avec "
                    "python -m migrations.baseline_legacy, puis appliquer sa baseline explicite"
                )
            if business_tables and not args.backup_confirmed:
                raise RuntimeError("Migration d'une base existante refusée sans --backup-confirmed")
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            inspect_legacy(connection, allow_post_baseline_tables=True)
            print(f"Schéma vérifié à head: {HEAD_REVISION}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
