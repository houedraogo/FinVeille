"""Archive log must never cascade: a journaled device cannot be physically deleted.

``device_archive_log.device_id`` cascaded on delete: removing a device erased the very journal that allows
restoring it, and ``merged_into_id`` silently became NULL when the kept device disappeared. Both foreign keys
become RESTRICT, so a physical ``DELETE`` of a device that carries journal rows (or is the kept device of an
archived duplicate) is refused by the database itself, whatever the code path (ORM, raw SQL, one-off script).

No data is touched. Only two constraints are replaced, on a table of a few thousand rows (instant).
``device_duplicate_candidates`` keeps ON DELETE CASCADE: a review-queue pair has no value without its devices.

Revision ID: c8e1f4a7b2d9
Revises: b7d3a91c5e24
"""
from alembic import op
import sqlalchemy as sa


revision = "c8e1f4a7b2d9"
down_revision = "b7d3a91c5e24"
branch_labels = None
depends_on = None

TABLE = "device_archive_log"


def _replace_fk(column: str, ondelete: str) -> None:
    """Drop the existing FK on ``column`` (whatever its generated name) and recreate it with ``ondelete``."""
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(TABLE):
        if fk["constrained_columns"] == [column] and fk["referred_table"] == "devices":
            op.drop_constraint(fk["name"], TABLE, type_="foreignkey")
    op.create_foreign_key(f"{TABLE}_{column}_fkey", TABLE, "devices", [column], ["id"], ondelete=ondelete)


def _fail_fast() -> None:
    """DROP/ADD CONSTRAINT queue behind running writers and block new ones behind it. Give up after 10 s instead of
    stalling the collectors and the API (the migration is transactional: nothing is left half-applied)."""
    op.execute("SET LOCAL lock_timeout = '10s'")


def upgrade() -> None:
    _fail_fast()
    _replace_fk("device_id", "RESTRICT")
    _replace_fk("merged_into_id", "RESTRICT")


def downgrade() -> None:
    _fail_fast()
    _replace_fk("device_id", "CASCADE")
    _replace_fk("merged_into_id", "SET NULL")
