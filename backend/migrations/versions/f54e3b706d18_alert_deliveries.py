"""Track confirmed instant alert deliveries.

Revision ID: f54e3b706d18
Revises: e910b53f2c64
"""
from alembic import op
import sqlalchemy as sa

revision = "f54e3b706d18"
down_revision = "e910b53f2c64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_deliveries",
        sa.Column("alert_id", sa.UUID(), sa.ForeignKey("alerts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("device_id", sa.UUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade interdit: conservation des preuves de livraison d'alertes")
