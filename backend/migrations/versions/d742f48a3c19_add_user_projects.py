"""Add the existing project model omitted from the initial Alembic inventory.

Revision ID: d742f48a3c19
Revises: 8c2f6e9a4b10
"""
from alembic import op
import sqlalchemy as sa


revision = "d742f48a3c19"
down_revision = "8c2f6e9a4b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "user_projects" in sa.inspect(op.get_bind()).get_table_names(schema="public"):
        raise RuntimeError("user_projects existe déjà: vérifier sa structure et ses données avant toute baseline")
    op.create_table(
        "user_projects",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sectors", sa.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("countries", sa.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("budget_min", sa.Numeric(15, 2), nullable=True),
        sa.Column("budget_max", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("keywords", sa.ARRAY(sa.Text()), nullable=True, server_default=sa.text("'{}'")),
        sa.Column("cached_matches", sa.JSON(), nullable=False),
        sa.Column("match_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
    )
    op.create_index("ix_user_projects_user_id", "user_projects", ["user_id"])
    op.create_index("ix_user_projects_organization_id", "user_projects", ["organization_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade interdit: user_projects peut contenir des projets clients")
