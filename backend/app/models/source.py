from sqlalchemy import Column, String, SmallInteger, Boolean, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    organism = Column(String(255), nullable=False)
    country = Column(String(100), nullable=False, index=True)
    region = Column(String(100))
    source_type = Column(String(50), nullable=False)
    # 'institution_publique' | 'agence_nationale' | 'portail_officiel' | 'institution_regionale' | 'autre'
    level = Column(SmallInteger, nullable=False, default=2, index=True)
    # 1=prioritaire, 2=secondaire, 3=relais
    url = Column(Text, nullable=False)
    collection_mode = Column(String(50), nullable=False)
    # 'api' | 'rss' | 'html' | 'dynamic' | 'pdf' | 'manual'
    check_frequency = Column(String(50), default="daily")
    # 'hourly' | 'daily' | 'weekly' | 'monthly'
    reliability = Column(SmallInteger, nullable=False, default=3)
    # 1 (faible) à 5 (très fiable)
    category = Column(String(20), nullable=False, default="public", index=True)
    # 'public' | 'private'
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    last_checked_at = Column(DateTime(timezone=True))
    last_success_at = Column(DateTime(timezone=True))
    consecutive_errors = Column(SmallInteger, default=0)
    config = Column(JSON)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
