"""Frozen schema checks shared by the legacy baseline and its repair revision.

The JSON manifest belongs to revision 5a37a54cae56. Do not regenerate it when
models change; add another Alembic revision instead.
"""
import json
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


SCHEMA = json.loads((Path(__file__).parent / "schema_5a37a54cae56.json").read_text(encoding="utf-8"))
BASELINE_REVISION = "5a37a54cae56"
SAFE_REQUIRED_ADDITIONS = {
    ("users", "platform_role"): "'member'",
    ("device_pipeline", "priority"): "'moyenne'",
    ("devices", "ai_rewrite_status"): "'pending'",
    ("devices", "ai_readiness_score"): "0",
    ("devices", "user_quality_score"): "0",
    ("plans", "is_active"): "true",
}


def _quote(connection, value):
    return connection.dialect.identifier_preparer.quote(value)


def _type_name(value):
    return value.compile(dialect=postgresql.dialect()).upper()


def _duplicates(connection, table, columns):
    quoted = ", ".join(_quote(connection, column) for column in columns)
    non_null = " AND ".join(f"{_quote(connection, column)} IS NOT NULL" for column in columns)
    sql = sa.text(
        f"SELECT 1 FROM {_quote(connection, table)} WHERE {non_null} GROUP BY {quoted} "
        f"HAVING count(*) > 1 LIMIT 1"
    )
    return connection.execute(sql).first() is not None


def inspect_legacy(connection, *, allow_post_baseline_tables=False):
    """Return only safe additive work; raise before any DDL on ambiguous data."""
    inspector = sa.inspect(connection)
    existing_tables = set(inspector.get_table_names(schema="public")) - {"alembic_version"}
    expected_tables = set(SCHEMA)
    if allow_post_baseline_tables:
        expected_tables.update({"user_projects", "stripe_webhook_events", "billing_checkouts", "alert_deliveries"})
    if existing_tables != expected_tables:
        raise RuntimeError(
            f"Schéma historique incomplet ou inconnu: tables absentes={sorted(expected_tables - existing_tables)}, "
            f"tables supplémentaires={sorted(existing_tables - expected_tables)}"
        )

    work = {"columns": [], "foreign_keys": [], "uniques": [], "indexes": []}
    for table_name, definition in SCHEMA.items():
        if inspector.get_pk_constraint(table_name)["constrained_columns"] != ["id"]:
            raise RuntimeError(f"Clé primaire incompatible: {table_name}.id")
        actual_columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        expected_columns = definition["columns"]
        extra = set(actual_columns) - set(expected_columns)
        if allow_post_baseline_tables and table_name == "subscriptions":
            extra -= {"cancel_at_period_end", "last_stripe_event_created", "last_stripe_event_id"}
        if extra:
            raise RuntimeError(f"Colonnes inconnues dans {table_name}: {sorted(extra)}")
        for column_name, expected in expected_columns.items():
            actual = actual_columns.get(column_name)
            if actual is None:
                if not expected["nullable"] and (table_name, column_name) not in SAFE_REQUIRED_ADDITIONS:
                    raise RuntimeError(f"Colonne obligatoire manquante sans reprise sûre: {table_name}.{column_name}")
                work["columns"].append((table_name, column_name, expected))
                continue
            actual_type = _type_name(actual["type"])
            if actual_type != expected["type"].upper():
                raise RuntimeError(
                    f"Type incompatible {table_name}.{column_name}: {actual_type} != {expected['type']}"
                )
            if bool(actual["nullable"]) != bool(expected["nullable"]):
                raise RuntimeError(f"Nullabilité incompatible: {table_name}.{column_name}")

        actual_fks = inspector.get_foreign_keys(table_name)
        for fk in definition["foreign_keys"]:
            matches = [item for item in actual_fks if item["constrained_columns"] == [fk["column"]]]
            if matches:
                item = matches[0]
                ondelete = (item.get("options") or {}).get("ondelete")
                if (item["referred_table"], item["referred_columns"], ondelete) != (
                    fk["target_table"], [fk["target_column"]], fk["ondelete"]
                ):
                    raise RuntimeError(f"Clé étrangère incompatible: {table_name}.{fk['column']}")
                continue
            if fk["column"] in actual_columns:
                source = _quote(connection, table_name)
                target = _quote(connection, fk["target_table"])
                col = _quote(connection, fk["column"])
                target_col = _quote(connection, fk["target_column"])
                orphan = connection.execute(sa.text(
                    f"SELECT 1 FROM {source} AS child WHERE child.{col} IS NOT NULL "
                    f"AND NOT EXISTS (SELECT 1 FROM {target} AS parent "
                    f"WHERE parent.{target_col} = child.{col}) LIMIT 1"
                )).first()
                if orphan:
                    raise RuntimeError(f"Données orphelines pour {table_name}.{fk['column']}; migration refusée")
            work["foreign_keys"].append((table_name, fk))

        actual_uniques = {item["name"]: item for item in inspector.get_unique_constraints(table_name)}
        for unique in definition["uniques"]:
            existing = (
                actual_uniques.get(unique["name"])
                if unique["name"] else next(
                    (item for item in actual_uniques.values() if item["column_names"] == unique["columns"]),
                    None,
                )
            )
            if existing:
                if existing["column_names"] != unique["columns"]:
                    raise RuntimeError(f"Contrainte UNIQUE incompatible: {unique['name']}")
            else:
                if set(unique["columns"]) <= set(actual_columns) and _duplicates(connection, table_name, unique["columns"]):
                    raise RuntimeError(f"Doublons avant contrainte UNIQUE: {unique['name']}")
                work["uniques"].append((table_name, unique))

        actual_indexes = {item["name"]: item for item in inspector.get_indexes(table_name)}
        for index in definition["indexes"]:
            existing = actual_indexes.get(index["name"])
            if existing:
                using = (existing.get("dialect_options") or {}).get("postgresql_using")
                if (existing["column_names"], bool(existing["unique"]), using or None) != (
                    index["columns"], bool(index["unique"]), index["using"] or None
                ):
                    raise RuntimeError(f"Index incompatible: {index['name']}")
            else:
                if index["unique"] and set(index["columns"]) <= set(actual_columns) and _duplicates(connection, table_name, index["columns"]):
                    raise RuntimeError(f"Doublons avant index UNIQUE: {index['name']}")
                work["indexes"].append((table_name, index))
    return work


def apply_additions(connection, work):
    """Apply the reviewed additive plan inside Alembic's PostgreSQL transaction."""
    for table, column, definition in work["columns"]:
        name = f"{_quote(connection, table)}.{_quote(connection, column)}"
        default = SAFE_REQUIRED_ADDITIONS.get((table, column))
        server_default = default or definition["server_default"]
        clause = f" DEFAULT {server_default}" if server_default else ""
        nullable = "" if definition["nullable"] else " NOT NULL"
        connection.execute(sa.text(
            f"ALTER TABLE {_quote(connection, table)} ADD COLUMN {_quote(connection, column)} "
            f"{definition['type']}{clause}{nullable}"
        ))
        if default and definition["server_default"] is None:
            connection.execute(sa.text(
                f"ALTER TABLE {_quote(connection, table)} ALTER COLUMN {_quote(connection, column)} DROP DEFAULT"
            ))

    for table, fk in work["foreign_keys"]:
        constraint = f"fk_{table}_{fk['column']}"
        ondelete = f" ON DELETE {fk['ondelete']}" if fk["ondelete"] else ""
        connection.execute(sa.text(
            f"ALTER TABLE {_quote(connection, table)} ADD CONSTRAINT {_quote(connection, constraint)} "
            f"FOREIGN KEY ({_quote(connection, fk['column'])}) REFERENCES "
            f"{_quote(connection, fk['target_table'])} ({_quote(connection, fk['target_column'])}){ondelete}"
        ))

    for table, unique in work["uniques"]:
        columns = ", ".join(_quote(connection, column) for column in unique["columns"])
        name = unique["name"] or f"uq_{table}_{'_'.join(unique['columns'])}"
        connection.execute(sa.text(
            f"ALTER TABLE {_quote(connection, table)} ADD CONSTRAINT {_quote(connection, name)} "
            f"UNIQUE ({columns})"
        ))

    for table, index in work["indexes"]:
        columns = ", ".join(_quote(connection, column) for column in index["columns"])
        unique = "UNIQUE " if index["unique"] else ""
        using = f" USING {index['using']}" if index["using"] else ""
        connection.execute(sa.text(
            f"CREATE {unique}INDEX {_quote(connection, index['name'])} "
            f"ON {_quote(connection, table)}{using} ({columns})"
        ))
