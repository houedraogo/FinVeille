from pydantic import BaseModel, field_validator
from typing import Optional, List, Literal
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal


class DeviceCreate(BaseModel):
    title: str
    organism: str
    country: str
    device_type: str
    source_url: str
    source_id: Optional[UUID] = None
    source_raw: Optional[str] = None
    organism_type: Optional[str] = None
    region: Optional[str] = None
    zone: Optional[str] = None
    geographic_scope: Optional[str] = None
    aid_nature: Optional[str] = None
    sectors: Optional[List[str]] = None
    beneficiaries: Optional[List[str]] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    eligibility_criteria: Optional[str] = None
    eligible_expenses: Optional[str] = None
    specific_conditions: Optional[str] = None
    required_documents: Optional[str] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None
    currency: str = "EUR"
    funding_rate: Optional[Decimal] = None
    funding_details: Optional[str] = None
    open_date: Optional[date] = None
    close_date: Optional[date] = None
    is_recurring: bool = False
    recurrence_notes: Optional[str] = None
    status: str = "open"
    language: str = "fr"
    keywords: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    source_raw: Optional[str] = None
    validation_status: Optional[str] = None


class DeviceUpdate(BaseModel):
    title: Optional[str] = None
    organism: Optional[str] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    eligibility_criteria: Optional[str] = None
    eligible_expenses: Optional[str] = None
    sectors: Optional[List[str]] = None
    beneficiaries: Optional[List[str]] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None
    funding_rate: Optional[Decimal] = None
    open_date: Optional[date] = None
    close_date: Optional[date] = None
    status: Optional[str] = None
    is_recurring: Optional[bool] = None
    keywords: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    specific_conditions: Optional[str] = None
    required_documents: Optional[str] = None


class DeviceResponse(BaseModel):
    id: UUID
    slug: Optional[str]
    title: str
    organism: str
    country: str
    region: Optional[str]
    zone: Optional[str]
    device_type: str
    aid_nature: Optional[str]
    sectors: Optional[List[str]]
    beneficiaries: Optional[List[str]]
    short_description: Optional[str]
    full_description: Optional[str]
    eligibility_criteria: Optional[str]
    eligible_expenses: Optional[str]
    specific_conditions: Optional[str]
    required_documents: Optional[str]
    amount_min: Optional[Decimal]
    amount_max: Optional[Decimal]
    currency: str
    funding_rate: Optional[Decimal]
    funding_details: Optional[str]
    open_date: Optional[date]
    close_date: Optional[date]
    is_recurring: bool
    recurrence_notes: Optional[str]
    status: str
    source_url: str
    source_id: Optional[UUID]
    source_raw: Optional[str] = None
    language: str
    keywords: Optional[List[str]]
    tags: Optional[List[str]]
    auto_summary: Optional[str]
    confidence_score: int
    completeness_score: int
    relevance_score: int
    validation_status: str
    first_seen_at: datetime
    last_verified_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeviceListResponse(BaseModel):
    items: List[DeviceResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BulkActionRequest(BaseModel):
    ids: List[UUID]
    action: Literal["validate", "reject", "delete", "tag"]
    tags: Optional[List[str]] = None  # requis si action == "tag"


class BulkActionResult(BaseModel):
    action: str
    processed: int
    failed: int
    errors: List[str] = []


class DeviceSearchParams(BaseModel):
    q: Optional[str] = None
    countries: Optional[List[str]] = None
    device_types: Optional[List[str]] = None
    sectors: Optional[List[str]] = None
    beneficiaries: Optional[List[str]] = None
    status: Optional[List[str]] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None
    close_date_before: Optional[date] = None
    close_date_after: Optional[date] = None
    closing_soon_days: Optional[int] = None
    source_id: Optional[UUID] = None
    min_confidence: Optional[int] = None
    validation_status: Optional[str] = None
    sort_by: str = "updated_at"
    sort_desc: bool = True
    page: int = 1
    page_size: int = 20
