from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserResponse


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    plan: str
    status: str
    created_by_id: Optional[UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationMemberResponse(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: str
    is_active: bool
    joined_at: datetime

    model_config = {"from_attributes": True}


class OrganizationInvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field("member", pattern="^(org_admin|member|viewer)$")
    organization_id: Optional[UUID] = None


class InvitationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    email: str
    role: str
    token: str
    invited_by_id: Optional[UUID]
    accepted_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class MeContextResponse(BaseModel):
    user: UserResponse
    current_organization: Optional[OrganizationResponse]
    memberships: List[OrganizationMemberResponse]
    permissions: Dict[str, bool]
