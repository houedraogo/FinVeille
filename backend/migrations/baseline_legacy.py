"""Explicit, checked baseline for an unversioned historical Kafundo database.

Run without options to check first. --stamp requires a separately verified backup and never
alters business tables. Follow it with `alembic upgrade head`.
"""
import argparse
import json

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import settings
from migrations.schema_contract import BASELINE_REVISION, inspect_legacy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stamp", action="store_true", help="Stamp the verified legacy schema at the baseline revision")
    parser.add_argument("--backup-confirmed", action="store_true", help="Confirm that a restorable backup was verified separately")
    args = parser.parse_args()
    if args.stamp and not args.backup_confirmed:
        parser.error("--stamp exige --backup-confirmed après vérification d'une sauvegarde restaurable")

    engine = create_engine(settings.DATABASE_SYNC_URL)
    try:
        with engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(42978122)"))
            tables = set(inspect(connection).get_table_names(schema="public"))
            if "alembic_version" in tables:
                versions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
                if versions:
                    raise RuntimeError(f"Base déjà versionnée ({versions}); utiliser alembic upgrade head")
            plan = inspect_legacy(connection)
            print(json.dumps({key: len(value) for key, value in plan.items()}, sort_keys=True))
            if args.stamp:
                config = Config("alembic.ini")
                config.attributes["connection"] = connection
                command.stamp(config, BASELINE_REVISION)
                print(f"Baseline appliquée: {BASELINE_REVISION}. Exécuter alembic upgrade head.")
            else:
                print("Contrôle réussi; aucune modification effectuée. Réaliser et vérifier une sauvegarde avant --stamp.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
