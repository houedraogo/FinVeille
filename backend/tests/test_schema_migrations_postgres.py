"""Disposable PostgreSQL integration tests for the two Alembic installation paths."""
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from migrations.schema_contract import BASELINE_REVISION, SCHEMA, inspect_legacy


ADMIN_URL = os.getenv("TEST_POSTGRES_MIGRATION_ADMIN_URL")
pytestmark = pytest.mark.skipif(
    not ADMIN_URL or os.getenv("KAFUNDO_MIGRATION_TESTS") != "1",
    reason="Dedicated disposable PostgreSQL admin URL and KAFUNDO_MIGRATION_TESTS=1 required",
)
ROOT = Path(__file__).resolve().parents[1]
HEAD = "3f8e2d1c9a05"
COUNTS = (
    "users", "organizations", "devices", "device_pipeline", "favorite_devices",
    "alerts", "funding_projects", "match_projects", "subscriptions", "billing_customers",
)


def _database_url(name):
    return ADMIN_URL.rsplit("/", 1)[0] + "/" + name


def _run(name, *arguments, expected=0, extra_env=None):
    sync_url = _database_url(name)
    env = os.environ.copy()
    env.update({
        "DATABASE_SYNC_URL": sync_url,
        "DATABASE_URL": sync_url.replace("postgresql://", "postgresql+asyncpg://", 1),
        "PYTHONPATH": str(ROOT),
        "DEBUG": "false",
    })
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, *arguments], cwd=ROOT, env=env, capture_output=True, text=True,
        timeout=60,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result.stdout + result.stderr


@pytest.fixture
def disposable_database():
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    names = []

    def create(copy_of=None):
        name = "kafundo_lot2_test_" + uuid4().hex[:20]
        assert name.replace("_", "").isalnum()
        sql = f"CREATE DATABASE {name}" + (f" TEMPLATE {copy_of}" if copy_of else "")
        with admin.connect() as connection:
            connection.execute(text(sql))
        names.append(name)
        return name

    yield create

    for name in reversed(names):
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE {name} WITH (FORCE)"))
    admin.dispose()


def _version(connection):
    return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def _counts(connection):
    return {table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() for table in COUNTS}


def _legacy(name):
    _run(name, "-m", "alembic", "upgrade", BASELINE_REVISION)
    sql = (ROOT / "tests" / "fixtures" / "legacy_schema_lot2.sql").read_text(encoding="utf-8")
    engine = create_engine(_database_url(name), isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.exec_driver_sql(sql)
    engine.dispose()


def _legacy_with_user_projects(name):
    _run(name, "-m", "alembic", "upgrade", BASELINE_REVISION)
    sql = (ROOT / "tests" / "fixtures" / "legacy_schema_lot2_with_user_projects.sql").read_text(encoding="utf-8")
    engine = create_engine(_database_url(name), isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.exec_driver_sql(sql)
    engine.dispose()


def test_empty_database_upgrade_head_and_idempotence(disposable_database):
    name = disposable_database()
    _run(name, "-m", "alembic", "upgrade", "head")
    engine = create_engine(_database_url(name))
    with engine.connect() as connection:
        assert _version(connection) == HEAD
        assert set(inspect(connection).get_table_names()) == set(SCHEMA) | {"alembic_version", "user_projects", "stripe_webhook_events", "billing_checkouts", "alert_deliveries"}
        assert not any(inspect_legacy(connection, allow_post_baseline_tables=True).values())
        assert connection.execute(text("SELECT count(*) FROM plans WHERE slug='free'")).scalar_one() == 1
        before = _counts(connection)
    engine.dispose()
    _run(name, "-m", "alembic", "upgrade", "head")
    engine = create_engine(_database_url(name))
    with engine.connect() as connection:
        assert _version(connection) == HEAD
        assert _counts(connection) == before
    engine.dispose()


def test_historical_baseline_and_upgrade_preserve_data(disposable_database):
    name = disposable_database()
    _legacy(name)
    engine = create_engine(_database_url(name))
    with engine.connect() as connection:
        before = _counts(connection)
        assert before == {table: 1 for table in COUNTS}
        note = connection.execute(text("SELECT note FROM device_pipeline")).scalar_one()
        representative = {
            "user": connection.execute(text("SELECT email FROM users")).scalar_one(),
            "organization": connection.execute(text("SELECT name FROM organizations")).scalar_one(),
            "device": connection.execute(text("SELECT title FROM devices")).scalar_one(),
            "alert": connection.execute(text("SELECT name FROM alerts")).scalar_one(),
            "project": connection.execute(text("SELECT name FROM funding_projects")).scalar_one(),
            "billing": connection.execute(text("SELECT stripe_customer_id FROM billing_customers")).scalar_one(),
        }
    engine.dispose()
    # A template copy is a controlled, restorable snapshot for this test.
    snapshot = disposable_database(copy_of=name)
    assert "Schema non vierge" in _run(snapshot, "-m", "alembic", "upgrade", "head", expected=1)
    assert "columns" in _run(name, "-m", "migrations.baseline_legacy")
    _run(name, "-m", "migrations.baseline_legacy", "--stamp", "--backup-confirmed")
    _run(name, "-m", "alembic", "upgrade", "head")
    engine = create_engine(_database_url(name))
    with engine.connect() as connection:
        assert _version(connection) == HEAD
        assert _counts(connection) == before
        assert connection.execute(text("SELECT note FROM device_pipeline")).scalar_one() == note
        assert connection.execute(text("SELECT priority FROM device_pipeline")).scalar_one() == "moyenne"
        assert connection.execute(text("SELECT default_organization_id FROM users")).scalar_one() is not None
        assert {
            "user": connection.execute(text("SELECT email FROM users")).scalar_one(),
            "organization": connection.execute(text("SELECT name FROM organizations")).scalar_one(),
            "device": connection.execute(text("SELECT title FROM devices")).scalar_one(),
            "alert": connection.execute(text("SELECT name FROM alerts")).scalar_one(),
            "project": connection.execute(text("SELECT name FROM funding_projects")).scalar_one(),
            "billing": connection.execute(text("SELECT stripe_customer_id FROM billing_customers")).scalar_one(),
        } == representative
        assert not any(inspect_legacy(connection, allow_post_baseline_tables=True).values())
    engine.dispose()
    _run(
        name, "-m", "pytest", "-q", "tests/test_schema_api_postgres.py", "-k", "signup_login",
        extra_env={"TEST_POSTGRES_DATABASE_URL": _database_url(name).replace("postgresql://", "postgresql+asyncpg://", 1)},
    )


def test_orphans_and_partial_schema_are_refused(disposable_database):
    orphan = disposable_database()
    _legacy(orphan)
    engine = create_engine(_database_url(orphan))
    with engine.begin() as connection:
        connection.execute(text("UPDATE users SET default_organization_id = '99999999-0000-0000-0000-000000000001'"))
    engine.dispose()
    output = _run(orphan, "-m", "migrations.baseline_legacy", expected=1)
    assert "orphelines" in output
    engine = create_engine(_database_url(orphan))
    with engine.connect() as connection:
        assert "alembic_version" not in inspect(connection).get_table_names()
        assert _counts(connection)["users"] == 1
    engine.dispose()

    partial = disposable_database()
    engine = create_engine(_database_url(partial))
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE unexpected_partial (id integer PRIMARY KEY)"))
    engine.dispose()
    assert "Schema non vierge" in _run(partial, "-m", "alembic", "upgrade", "head", expected=1)
    assert "incomplet ou inconnu" in _run(partial, "-m", "migrations.baseline_legacy", expected=1)


def test_incompatible_type_refused_before_stamp(disposable_database):
    name = disposable_database()
    _legacy(name)
    engine = create_engine(_database_url(name))
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(10)"))
    engine.dispose()
    assert "Type incompatible" in _run(name, "-m", "migrations.baseline_legacy", expected=1)


def test_historical_baseline_with_preexisting_user_projects(disposable_database):
    """Production scenario: user_projects pre-exists baseline (0 rows); baseline must accept it and
    alembic upgrade head must skip recreation without error."""
    name = disposable_database()
    _legacy_with_user_projects(name)
    engine = create_engine(_database_url(name))
    with engine.connect() as connection:
        before = _counts(connection)
        assert before == {table: 1 for table in COUNTS}
        assert "alembic_version" not in inspect(connection).get_table_names()
        assert "user_projects" in inspect(connection).get_table_names()
        assert connection.execute(text("SELECT count(*) FROM user_projects")).scalar_one() == 0
    engine.dispose()
    assert "columns" in _run(name, "-m", "migrations.baseline_legacy")
    _run(name, "-m", "migrations.baseline_legacy", "--stamp", "--backup-confirmed")
    _run(name, "-m", "alembic", "upgrade", "head")
    engine = create_engine(_database_url(name))
    with engine.connect() as connection:
        assert _version(connection) == HEAD
        assert _counts(connection) == before
        assert "user_projects" in inspect(connection).get_table_names()
        assert connection.execute(text("SELECT count(*) FROM user_projects")).scalar_one() == 0
        assert not any(inspect_legacy(connection, allow_post_baseline_tables=True).values())
    engine.dispose()


def test_failed_repair_rolls_back_and_does_not_advance_version(disposable_database):
    name = disposable_database()
    _legacy(name)
    _run(name, "-m", "migrations.baseline_legacy", "--stamp", "--backup-confirmed")
    engine = create_engine(_database_url(name))
    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE users SET default_organization_id = '99999999-0000-0000-0000-000000000001'"
        ))
    engine.dispose()
    assert "orphelines" in _run(name, "-m", "alembic", "upgrade", "head", expected=1)
    engine = create_engine(_database_url(name))
    with engine.connect() as connection:
        assert _version(connection) == BASELINE_REVISION
        assert _counts(connection) == {table: 1 for table in COUNTS}
        assert "country" not in {column["name"] for column in inspect(connection).get_columns("users")}
    engine.dispose()
