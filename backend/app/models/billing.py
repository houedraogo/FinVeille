import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text)
    price_monthly_eur = Column(Integer, nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="EUR")
    limits = Column(JSON, nullable=False, default=dict)
    features = Column(JSON, nullable=False, default=dict)
    stripe_price_id = Column(String(255))
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_subscription_organization"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="active")
    stripe_subscription_id = Column(String(255))
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(120), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    event_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BillingCustomer(Base):
    __tablename__ = "billing_customers"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_billing_customer_organization"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    stripe_customer_id = Column(String(255), unique=True, nullable=True, index=True)
    billing_email = Column(String(255))
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
