from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class PasswordForgotRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    token: str = Field(..., min_length=20)
    new_password: str = Field(..., min_length=8)


class DataExportResponse(BaseModel):
    id: UUID
    status: str
    export_type: str
    download_token: str
    payload: Dict[str, Any]
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class DeletionRequestCreate(BaseModel):
    reason: Optional[str] = None


class DeletionRequestResponse(BaseModel):
    id: UUID
    status: str
    reason: Optional[str]
    scheduled_for: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    organization_id: Optional[UUID]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    ip_address: Optional[str]
    metadata_json: Dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
