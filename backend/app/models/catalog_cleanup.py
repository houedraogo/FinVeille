"""Tables du nettoyage du catalogue (octobre 2026).

* DeviceArchiveLog        : journal réversible de chaque archivage (anciennes valeurs).
* DeviceRejection         : quarantaine — une fiche rejetée n'est pas réimportée à
                            chaque collecte tant que son contenu ne change pas.
* DuplicateCandidate      : file de revue des doublons probables (jamais fusionnés
                            automatiquement).

Rien n'est supprimé physiquement : une fiche archivée reste en base avec son
identifiant, de sorte que toute référence externe (dossiers clients
Finnovatix via kafundo_id, favoris, pipelines) reste valide.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base

ARCHIVED_STATUS = "archived"
AI_HELD_STATUS = "on_hold"


class DeviceArchiveLog(Base):
    __tablename__ = "device_archive_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String(64), nullable=False, index=True)
    batch = Column(String(40), nullable=False, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    rule = Column(String(80))
    reason = Column(Text)
    merged_into_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"))
    previous_validation_status = Column(String(50))
    previous_status = Column(String(50))
    previous_user_quality_decision = Column(String(50))
    previous_ai_rewrite_status = Column(String(50))
    previous_tags = Column(JSON)
    # archive | ai_hold : ce que l'opération a changé (ai_hold ne touche que le statut IA)
    action = Column(String(20), nullable=False, default="archive")
    # Références utilisateur déplacées vers la fiche conservée (pour pouvoir les remettre à la restauration).
    moved_references = Column(JSON)
    archived_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    restored_at = Column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("run_id", "device_id", name="uq_device_archive_log_run_device"),
    )


class DeviceRejection(Base):
    __tablename__ = "device_rejections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), index=True)
    canonical_url = Column(Text, nullable=False)
    title = Column(Text)
    content_hash = Column(String(64))
    rule = Column(String(80), nullable=False)
    reason = Column(Text)
    decided_by = Column(String(80), nullable=False, default="system")
    decided_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_device_rejections_canonical_url", "canonical_url"),
        UniqueConstraint("source_id", "canonical_url", name="uq_device_rejections_source_url"),
    )


class DuplicateCandidate(Base):
    __tablename__ = "device_duplicate_candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    other_device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    tier = Column(String(20), nullable=False)
    reasons = Column(JSON)
    status = Column(String(20), nullable=False, default="open", index=True)  # open | merged | dismissed
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True))
    reviewed_by = Column(String(80))

    __table_args__ = (
        UniqueConstraint("device_id", "other_device_id", name="uq_device_duplicate_pair"),
    )
