from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


class AlertCreate(BaseModel):
    name: str
    criteria: Dict[str, Any] = {}
    frequency: str = "daily"
    channels: List[str] = ["email", "dashboard"]
    alert_types: List[str] = ["new", "updated", "closing_soon"]
    is_active: bool = True


class AlertUpdate(BaseModel):
    name: Optional[str] = None
    criteria: Optional[Dict[str, Any]] = None
    frequency: Optional[str] = None
    channels: Optional[List[str]] = None
    alert_types: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AlertResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    criteria: Dict[str, Any]
    frequency: str
    channels: List[str]
    alert_types: List[str]
    is_active: bool
    last_triggered_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
