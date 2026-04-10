from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database import Base


class DeviceHistory(Base):
    __tablename__ = "device_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    changed_by = Column(String(100))  # 'system' ou user_id
    change_type = Column(String(50))
    # 'created' | 'updated' | 'status_change' | 'validated' | 'rejected' | 'deleted'
    diff = Column(JSON)
    source_hash = Column(String(64))
