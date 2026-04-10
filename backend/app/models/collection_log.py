from sqlalchemy import Column, String, Integer, SmallInteger, DateTime, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database import Base


class CollectionLog(Base):
    __tablename__ = "collection_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ended_at = Column(DateTime(timezone=True))
    status = Column(String(50), nullable=False, default="running")
    # 'running' | 'success' | 'partial' | 'failed'
    items_found = Column(Integer, default=0)
    items_new = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    items_skipped = Column(Integer, default=0)
    items_error = Column(Integer, default=0)
    error_message = Column(Text)
    details = Column(JSON)
