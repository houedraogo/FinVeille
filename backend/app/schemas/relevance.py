from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.device import DeviceResponse


class OrganizationProfilePayload(BaseModel):
    organization_type: Optional[str] = None
    legal_form: Optional[str] = None
    team_size: Optional[str] = None
    annual_budget_range: Optional[str] = None
    development_stage: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    countries: Optional[list[str]] = None
    regions: Optional[list[str]] = None
    sectors: Optional[list[str]] = None
    target_funding_types: Optional[list[str]] = None
    preferred_ticket_min: Optional[Decimal] = None
    preferred_ticket_max: Optional[Decimal] = None
    currency: str = "EUR"
    strategic_priorities: Optional[list[str]] = None


class OrganizationProfileResponse(OrganizationProfilePayload):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FundingProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    summary: Optional[str] = None
    countries: Optional[list[str]] = None
    sectors: Optional[list[str]] = None
    beneficiaries: Optional[list[str]] = None
    target_funding_types: Optional[list[str]] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    timeline_months: Optional[int] = Field(default=None, ge=1, le=120)
    status: str = "active"
    is_primary: bool = False


class FundingProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    summary: Optional[str] = None
    countries: Optional[list[str]] = None
    sectors: Optional[list[str]] = None
    beneficiaries: Optional[list[str]] = None
    target_funding_types: Optional[list[str]] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    timeline_months: Optional[int] = Field(default=None, ge=1, le=120)
    status: Optional[str] = None
    is_primary: Optional[bool] = None


class FundingProjectResponse(BaseModel):
    id: UUID
    organization_id: UUID
    created_by_id: Optional[UUID]
    name: str
    summary: Optional[str]
    countries: Optional[list[str]]
    sectors: Optional[list[str]]
    beneficiaries: Optional[list[str]]
    target_funding_types: Optional[list[str]]
    budget_min: Optional[Decimal]
    budget_max: Optional[Decimal]
    timeline_months: Optional[int]
    status: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeviceRelevanceResponse(BaseModel):
    device_id: UUID
    organization_id: UUID
    funding_project_id: Optional[UUID] = None
    relevance_score: int
    relevance_label: str
    priority_level: str
    eligibility_confidence: str
    decision_hint: str
    reason_codes: list[str]
    reason_texts: list[str]
    computed_at: datetime


class RecommendationItem(BaseModel):
    device: DeviceResponse
    relevance: DeviceRelevanceResponse


class RecommendationListResponse(BaseModel):
    items: list[RecommendationItem]
    total: int
    page: int
    page_size: int
    pages: int
