from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy import Text
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)

    # Critères de filtrage (JSON flexible)
    criteria = Column(JSON, nullable=False, default=dict)
    # Exemple :
    # {
    #   "countries": ["France"],
    #   "sectors": ["energie"],
    #   "device_types": ["aap", "subvention"],
    #   "beneficiaries": ["startup"],
    #   "keywords": ["transition"],
    #   "amount_min": 10000,
    #   "close_within_days": 30
    # }

    frequency = Column(String(20), default="daily")
    # 'instant' | 'daily' | 'weekly'
    channels = Column(ARRAY(Text), default=list)
    # ['email', 'dashboard']
    alert_types = Column(ARRAY(Text), default=list)
    # ['new', 'updated', 'closing_soon', 'status_change']

    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
