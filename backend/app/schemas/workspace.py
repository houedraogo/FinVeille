from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Documents pipeline ────────────────────────────────────────────────────────

class PipelineDocumentAdd(BaseModel):
    """Attacher un document (URL externe ou note) à une candidature pipeline."""
    name: str = Field(..., min_length=1, max_length=255, description="Nom affiché")
    url: Optional[str] = Field(None, max_length=2000, description="Lien externe (Drive, Dropbox…)")
    doc_type: str = Field("url", description="url | note | brouillon")
    note: Optional[str] = Field(None, max_length=1000, description="Note libre")


class PipelineDocumentItem(BaseModel):
    id: str
    name: str
    url: Optional[str] = None
    doc_type: str = "url"
    note: Optional[str] = None
    added_at: str  # ISO datetime string


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
    priority: str = Field("moyenne", max_length=20)
    reminder_date: Optional[date] = None
    match_project_id: Optional[UUID] = None
    note: str = ""
    documents: Optional[List[Dict[str, Any]]] = None
    snapshot: Dict[str, Any] = Field(default_factory=dict)


class DevicePipelineResponse(BaseModel):
    device_id: UUID
    pipeline_status: str
    priority: str = "moyenne"
    reminder_date: Optional[date] = None
    match_project_id: Optional[UUID] = None
    note: str
    documents: Optional[List[Dict[str, Any]]] = None
    snapshot: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]


# ─── Team view ────────────────────────────────────────────────────────────────

class TeamMemberPipelineItem(BaseModel):
    device_id: UUID
    pipeline_status: str
    priority: str
    note: str
    documents_count: int
    snapshot: Dict[str, Any]
    updated_at: Optional[datetime]


class TeamMemberResponse(BaseModel):
    user_id: UUID
    full_name: Optional[str]
    email: str
    role: str
    pipeline: List[TeamMemberPipelineItem]


class TeamViewResponse(BaseModel):
    organization_id: Optional[UUID]
    organization_name: Optional[str]
    members: List[TeamMemberResponse]


# ─── Activity feed ────────────────────────────────────────────────────────────

class ActivityItem(BaseModel):
    id: str
    activity_type: str   # "pipeline_add" | "pipeline_update" | "favorite_add" | "match_created" | "document_add"
    label: str           # titre court de l'action
    description: str     # détail
    device_id: Optional[str] = None
    device_title: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    occurred_at: datetime


class ActivityFeedResponse(BaseModel):
    items: List[ActivityItem]
    total: int


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
