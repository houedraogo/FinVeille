"""Catalogue cleanup support tables: archive log, rejection quarantine, duplicate review queue.

Purely additive (three new tables, no change to existing ones). No data is
touched; the tables are populated only by the explicitly confirmed cleanup
tooling and the collectors' scope/duplicate checks.

Revision ID: b7d3a91c5e24
Revises: 3f8e2d1c9a05
"""
from alembic import op
import sqlalchemy as sa


revision = "b7d3a91c5e24"
down_revision = "3f8e2d1c9a05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_archive_log",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("batch", sa.String(40), nullable=False),
        sa.Column("device_id", sa.UUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule", sa.String(80)),
        sa.Column("reason", sa.Text()),
        sa.Column("merged_into_id", sa.UUID(), sa.ForeignKey("devices.id", ondelete="SET NULL")),
        sa.Column("previous_validation_status", sa.String(50)),
        sa.Column("previous_status", sa.String(50)),
        sa.Column("previous_user_quality_decision", sa.String(50)),
        sa.Column("previous_ai_rewrite_status", sa.String(50)),
        sa.Column("previous_tags", sa.JSON()),
        sa.Column("archived_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("run_id", "device_id", name="uq_device_archive_log_run_device"),
    )
    op.create_index("ix_device_archive_log_run_id", "device_archive_log", ["run_id"])
    op.create_index("ix_device_archive_log_batch", "device_archive_log", ["batch"])
    op.create_index("ix_device_archive_log_device_id", "device_archive_log", ["device_id"])

    op.create_table(
        "device_rejections",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("source_id", sa.UUID(), sa.ForeignKey("sources.id", ondelete="SET NULL")),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("rule", sa.String(80), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("decided_by", sa.String(80), nullable=False, server_default="system"),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source_id", "canonical_url", name="uq_device_rejections_source_url"),
    )
    op.create_index("ix_device_rejections_source_id", "device_rejections", ["source_id"])
    op.create_index("ix_device_rejections_canonical_url", "device_rejections", ["canonical_url"])

    op.create_table(
        "device_duplicate_candidates",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("device_id", sa.UUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("other_device_id", sa.UUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("reasons", sa.JSON()),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(80)),
        sa.UniqueConstraint("device_id", "other_device_id", name="uq_device_duplicate_pair"),
    )
    op.create_index("ix_device_duplicate_candidates_device_id", "device_duplicate_candidates", ["device_id"])
    op.create_index("ix_device_duplicate_candidates_other_device_id", "device_duplicate_candidates", ["other_device_id"])
    op.create_index("ix_device_duplicate_candidates_status", "device_duplicate_candidates", ["status"])


def downgrade() -> None:
    raise RuntimeError("Downgrade interdit: conservation du journal d'archivage et des décisions de quarantaine")
