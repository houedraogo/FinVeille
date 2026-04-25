from sqlalchemy import (
    Column, String, SmallInteger, Boolean, Text, Date, DateTime,
    Numeric, ForeignKey, Index, JSON
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    # --- Identité ---
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(300), unique=True)
    title = Column(String(500), nullable=False)
    title_normalized = Column(String(500))

    # --- Émetteur ---
    organism = Column(String(255), nullable=False)
    organism_type = Column(String(100))

    # --- Géographie ---
    country = Column(String(100), nullable=False, index=True)
    region = Column(String(200))
    zone = Column(String(200))
    geographic_scope = Column(String(50))
    # 'national' | 'regional' | 'local' | 'continental' | 'international'

    # --- Classification ---
    device_type = Column(String(100), nullable=False, index=True)
    # 'subvention' | 'pret' | 'avance_remboursable' | 'garantie' | 'credit_impot'
    # | 'exoneration' | 'aap' | 'ami' | 'accompagnement' | 'concours' | 'autre'
    aid_nature = Column(String(100))
    sectors = Column(ARRAY(Text))
    beneficiaries = Column(ARRAY(Text))

    # --- Descriptions ---
    short_description = Column(Text)
    full_description = Column(Text)
    content_sections_json = Column(JSON)
    ai_rewritten_sections_json = Column(JSON)
    ai_rewrite_status = Column(String(50), default="pending", index=True)
    ai_rewrite_model = Column(String(120))
    ai_rewrite_checked_at = Column(DateTime(timezone=True))
    eligibility_criteria = Column(Text)
    eligible_expenses = Column(Text)
    specific_conditions = Column(Text)
    required_documents = Column(Text)

    # --- Financement ---
    amount_min = Column(Numeric(15, 2))
    amount_max = Column(Numeric(15, 2))
    currency = Column(String(10), default="EUR")
    funding_rate = Column(Numeric(5, 2))
    funding_details = Column(Text)

    # --- Dates ---
    open_date = Column(Date)
    close_date = Column(Date, index=True)
    is_recurring = Column(Boolean, default=False)
    recurrence_notes = Column(Text)

    # --- Statut ---
    status = Column(String(50), nullable=False, default="open", index=True)
    # 'open' | 'closed' | 'recurring' | 'standby' | 'expired' | 'unknown'

    # --- Source & qualité ---
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), index=True)
    source_url = Column(Text, nullable=False)
    source_raw = Column(Text)
    source_hash = Column(String(64))

    # --- Métadonnées ---
    language = Column(String(10), default="fr")
    keywords = Column(ARRAY(Text))
    tags = Column(ARRAY(Text))
    auto_summary = Column(Text)
    confidence_score = Column(SmallInteger, default=0)
    completeness_score = Column(SmallInteger, default=0)
    relevance_score = Column(SmallInteger, default=0)
    ai_readiness_score = Column(SmallInteger, default=0)
    ai_readiness_label = Column(String(80))
    ai_readiness_reasons = Column(ARRAY(Text))

    # --- Workflow validation ---
    validation_status = Column(String(50), default="auto_published", index=True)
    # 'pending_review' | 'approved' | 'rejected' | 'auto_published'
    validated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    validated_at = Column(DateTime(timezone=True))

    # --- Analyse décisionnelle IA ---
    decision_analysis = Column(JSON, nullable=True)
    # Structure: {
    #   "go_no_go": "go" | "no_go" | "a_verifier",
    #   "recommended_priority": "haute" | "moyenne" | "faible",
    #   "why_interesting": str,
    #   "why_cautious": str,
    #   "points_to_confirm": str,
    #   "recommended_action": str,
    #   "urgency_level": "critique" | "haute" | "moyenne" | "faible",
    #   "difficulty_level": "faible" | "moyenne" | "haute",
    #   "effort_level": "faible" | "moyenne" | "haute",
    #   "eligibility_score": 0-100,
    #   "strategic_interest": 0-100,
    #   "model": str,
    # }
    decision_analyzed_at = Column(DateTime(timezone=True), nullable=True)

    # --- Timestamps ---
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_verified_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Recherche full-text ---
    search_vector = Column(TSVECTOR)

    # --- Relations ---
    source = relationship("Source", lazy="select", foreign_keys=[source_id])

    __table_args__ = (
        Index("idx_devices_sectors", sectors, postgresql_using="gin"),
        Index("idx_devices_beneficiaries", beneficiaries, postgresql_using="gin"),
        Index("idx_devices_keywords", keywords, postgresql_using="gin"),
        Index("idx_devices_search_vector", "search_vector", postgresql_using="gin"),
    )
