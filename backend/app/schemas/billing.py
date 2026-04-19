from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PlanResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    description: Optional[str]
    price_monthly_eur: int
    currency: str
    limits: Dict[str, Any]
    features: Dict[str, Any]
    sort_order: int

    model_config = {"from_attributes": True}


class SubscriptionResponse(BaseModel):
    plan: PlanResponse
    subscription_status: str
    organization_id: Optional[UUID]
    current_period_end: Optional[datetime]
    usage: Dict[str, int]
    limits: Dict[str, Any]
    features: Dict[str, Any]


class CheckoutRequest(BaseModel):
    plan_slug: str = Field(..., min_length=2, max_length=80)


class CheckoutResponse(BaseModel):
    checkout_url: str
    configured: bool
    message: str


class BillingPortalResponse(BaseModel):
    portal_url: str
    configured: bool
    message: str
