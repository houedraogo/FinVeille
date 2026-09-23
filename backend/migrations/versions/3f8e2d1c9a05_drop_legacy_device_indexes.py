"""Drop device indexes that exist in the legacy DB but are absent from the ORM models.

These two indexes were created by the old create_all() startup path.  They are not
declared on the SQLAlchemy model columns, so alembic check reports them as pending
'remove_index' operations.  Drop them to bring the schema in line with the models.

Revision ID: 3f8e2d1c9a05
Revises: f54e3b706d18
"""
from alembic import op
import sqlalchemy as sa


revision = "3f8e2d1c9a05"
down_revision = "f54e3b706d18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    indexes = {row[0] for row in conn.execute(sa.text(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'devices' AND schemaname = 'public'"
    ))}
    if "ix_devices_ai_readiness_label" in indexes:
        op.drop_index("ix_devices_ai_readiness_label", table_name="devices")
    if "ix_devices_user_quality_decision" in indexes:
        op.drop_index("ix_devices_user_quality_decision", table_name="devices")


def downgrade() -> None:
    op.create_index("ix_devices_ai_readiness_label", "devices", ["ai_readiness_label"])
    op.create_index("ix_devices_user_quality_decision", "devices", ["user_quality_decision"])
