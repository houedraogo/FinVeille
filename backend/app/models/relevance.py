import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.sql import func

from app.database import Base


class OrganizationProfile(Base):
    __tablename__ = "organization_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_organization_profile_organization"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_type = Column(String(80), nullable=True)
    legal_form = Column(String(120), nullable=True)
    team_size = Column(String(50), nullable=True)
    annual_budget_range = Column(String(80), nullable=True)
    development_stage = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    website = Column(String(500), nullable=True)
    countries = Column(ARRAY(Text), nullable=True)
    regions = Column(ARRAY(Text), nullable=True)
    sectors = Column(ARRAY(Text), nullable=True)
    target_funding_types = Column(ARRAY(Text), nullable=True)
    preferred_ticket_min = Column(Numeric(15, 2), nullable=True)
    preferred_ticket_max = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(10), nullable=False, default="EUR")
    strategic_priorities = Column(ARRAY(Text), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FundingProject(Base):
    __tablename__ = "funding_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    countries = Column(ARRAY(Text), nullable=True)
    sectors = Column(ARRAY(Text), nullable=True)
    beneficiaries = Column(ARRAY(Text), nullable=True)
    target_funding_types = Column(ARRAY(Text), nullable=True)
    budget_min = Column(Numeric(15, 2), nullable=True)
    budget_max = Column(Numeric(15, 2), nullable=True)
    timeline_months = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default="active")
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DeviceRelevanceCache(Base):
    __tablename__ = "device_relevance_cache"
    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "organization_id",
            "funding_project_id",
            name="uq_device_relevance_cache_scope",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    funding_project_id = Column(UUID(as_uuid=True), ForeignKey("funding_projects.id", ondelete="CASCADE"), nullable=True, index=True)
    relevance_score = Column(Integer, nullable=False, default=0)
    relevance_label = Column(String(120), nullable=True)
    priority_level = Column(String(40), nullable=True)
    eligibility_confidence = Column(String(40), nullable=True)
    decision_hint = Column(Text, nullable=True)
    reason_codes = Column(JSON, nullable=True)
    reason_texts = Column(JSON, nullable=True)
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
