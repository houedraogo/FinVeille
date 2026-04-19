from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SavedSearchBase(BaseModel):
    id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    path: Optional[str] = Field(None, max_length=255)
    filters: Dict[str, Any] = Field(default_factory=dict)
    result_count: Optional[int] = None


class SavedSearchCreate(SavedSearchBase):
    pass


class SavedSearchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    path: Optional[str] = Field(None, max_length=255)
    filters: Optional[Dict[str, Any]] = None
    result_count: Optional[int] = None


class SavedSearchResponse(BaseModel):
    id: UUID
    name: str
    title: Optional[str]
    path: Optional[str]
    filters: Dict[str, Any]
    result_count: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]


class FavoriteDeviceCreate(BaseModel):
    device_id: UUID
    snapshot: Dict[str, Any] = Field(default_factory=dict)


class FavoriteDeviceResponse(BaseModel):
    device_id: UUID
    snapshot: Dict[str, Any]
    created_at: datetime


class DevicePipelineCreate(BaseModel):
    device_id: UUID
    pipeline_status: str = Field(..., min_length=1, max_length=80)
    note: str = ""
    snapshot: Dict[str, Any] = Field(default_factory=dict)


class DevicePipelineResponse(BaseModel):
    device_id: UUID
    pipeline_status: str
    note: str
    snapshot: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]


class UserPreferencesPayload(BaseModel):
    preferences: Dict[str, Any] = Field(default_factory=dict)


class UserPreferencesResponse(BaseModel):
    preferences: Dict[str, Any]
    updated_at: Optional[datetime] = None


class MatchProjectCreate(BaseModel):
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    result: Dict[str, Any] = Field(default_factory=dict)


class MatchProjectResponse(BaseModel):
    id: UUID
    file_name: Optional[str]
    file_size: Optional[int]
    result: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]


class WorkspaceSnapshotResponse(BaseModel):
    saved_searches: List[SavedSearchResponse]
    favorites: List[FavoriteDeviceResponse]
    pipeline: List[DevicePipelineResponse]
    preferences: UserPreferencesResponse
    match_projects: List[MatchProjectResponse]
