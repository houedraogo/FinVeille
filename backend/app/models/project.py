import uuid

from sqlalchemy import Column, String, Text, Numeric, JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func

from app.database import Base

# stage: ideation → mvp → croissance → expansion → maturite
PROJECT_STAGES = ["ideation", "mvp", "croissance", "expansion", "maturite"]


class UserProject(Base):
    __tablename__ = "user_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)

    name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    sectors = Column(ARRAY(Text), nullable=False, server_default="{}")
    countries = Column(ARRAY(Text), nullable=False, server_default="{}")
    stage = Column(String(50), nullable=False, default="ideation")
    budget_min = Column(Numeric(15, 2), nullable=True)
    budget_max = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(10), default="EUR")
    keywords = Column(ARRAY(Text), nullable=True, server_default="{}")

    # Résultats de matching mis en cache (rafraîchis à la demande)
    cached_matches = Column(JSON, nullable=False, default=list)
    match_score = Column(Numeric(5, 2), nullable=True)
    matched_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
