"""Track Stripe event freshness and one outstanding checkout per organization.

Revision ID: e910b53f2c64
Revises: d742f48a3c19
"""
from alembic import op
import sqlalchemy as sa

revision = "e910b53f2c64"
down_revision = "d742f48a3c19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("subscriptions", sa.Column("last_stripe_event_created", sa.BigInteger(), nullable=True))
    op.add_column("subscriptions", sa.Column("last_stripe_event_id", sa.String(255), nullable=True))
    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("stripe_created", sa.BigInteger(), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "billing_checkouts",
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("plan_id", sa.UUID(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("stripe_session_id", sa.String(255), nullable=False),
        sa.Column("checkout_url", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade interdit: le ledger Stripe protège les abonnements clients")
