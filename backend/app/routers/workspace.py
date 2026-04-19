from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.organization import OrganizationMember
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.models.workspace import DevicePipeline, FavoriteDevice, MatchProject, UserPreferences
from app.schemas.workspace import (
    DevicePipelineCreate,
    DevicePipelineResponse,
    FavoriteDeviceCreate,
    FavoriteDeviceResponse,
    MatchProjectCreate,
    MatchProjectResponse,
    SavedSearchCreate,
    SavedSearchResponse,
    SavedSearchUpdate,
    UserPreferencesPayload,
    UserPreferencesResponse,
    WorkspaceSnapshotResponse,
)
from app.services.billing_service import ensure_limit

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])

DEFAULT_PREFERENCES = {
    "defaultViewMode": "cards",
    "emailDigest": True,
    "productTips": True,
}


async def _current_organization_id(db: AsyncSession, user: User) -> UUID | None:
    result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user.id, OrganizationMember.is_active == True)
        .order_by(OrganizationMember.joined_at.asc())
    )
    memberships = list(result.scalars().all())
    if not memberships:
        return None
    if user.default_organization_id:
        for membership in memberships:
            if membership.organization_id == user.default_organization_id:
                return membership.organization_id
    return memberships[0].organization_id


def _saved_search_response(item: SavedSearch) -> SavedSearchResponse:
    return SavedSearchResponse(
        id=item.id,
        name=item.name,
        title=item.title,
        path=item.path,
        filters=item.query or {},
        result_count=item.result_count,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _favorite_response(item: FavoriteDevice) -> FavoriteDeviceResponse:
    return FavoriteDeviceResponse(
        device_id=item.device_id,
        snapshot=item.snapshot or {},
        created_at=item.created_at,
    )


def _pipeline_response(item: DevicePipeline) -> DevicePipelineResponse:
    return DevicePipelineResponse(
        device_id=item.device_id,
        pipeline_status=item.pipeline_status,
        note=item.note or "",
        snapshot=item.snapshot or {},
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _preferences_response(item: UserPreferences | None) -> UserPreferencesResponse:
    if not item:
        return UserPreferencesResponse(preferences=DEFAULT_PREFERENCES, updated_at=None)
    return UserPreferencesResponse(
        preferences={**DEFAULT_PREFERENCES, **(item.preferences or {})},
        updated_at=item.updated_at,
    )


def _match_response(item: MatchProject) -> MatchProjectResponse:
    return MatchProjectResponse(
        id=item.id,
        file_name=item.file_name,
        file_size=item.file_size,
        result=item.result or {},
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=WorkspaceSnapshotResponse)
async def get_workspace_snapshot(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved = await list_saved_searches(db, current_user)
    favorites = await list_favorites(db, current_user)
    pipeline = await list_pipeline(db, current_user)
    preferences = await get_preferences(db, current_user)
    matches = await list_match_projects(db, current_user)
    return WorkspaceSnapshotResponse(
        saved_searches=saved,
        favorites=favorites,
        pipeline=pipeline,
        preferences=preferences,
        match_projects=matches,
    )


@router.get("/saved-searches", response_model=list[SavedSearchResponse])
async def list_saved_searches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SavedSearch)
        .where(SavedSearch.user_id == current_user.id)
        .order_by(SavedSearch.updated_at.desc().nullslast(), SavedSearch.created_at.desc())
    )
    return [_saved_search_response(item) for item in result.scalars().all()]


@router.post("/saved-searches", response_model=SavedSearchResponse, status_code=201)
async def create_saved_search(
    data: SavedSearchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = None
    if data.id:
        result = await db.execute(
            select(SavedSearch).where(SavedSearch.id == data.id, SavedSearch.user_id == current_user.id)
        )
        existing = result.scalar_one_or_none()

    organization_id = await _current_organization_id(db, current_user)
    if existing:
        existing.name = data.name
        existing.title = data.title
        existing.path = data.path
        existing.query = data.filters
        existing.result_count = data.result_count
        item = existing
    else:
        await ensure_limit(db, current_user, "saved_searches")
        values = {
            "user_id": current_user.id,
            "organization_id": organization_id,
            "name": data.name,
            "title": data.title,
            "path": data.path,
            "query": data.filters,
            "result_count": data.result_count,
        }
        if data.id:
            values["id"] = data.id
        item = SavedSearch(**values)
        db.add(item)

    await db.commit()
    await db.refresh(item)
    return _saved_search_response(item)


@router.put("/saved-searches/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: UUID,
    data: SavedSearchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Recherche sauvegardee introuvable.")

    payload = data.model_dump(exclude_unset=True)
    if "filters" in payload:
        item.query = payload.pop("filters")
    if "result_count" in payload:
        item.result_count = payload.pop("result_count")
    for field, value in payload.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return _saved_search_response(item)


@router.delete("/saved-searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
    return None


@router.get("/favorites", response_model=list[FavoriteDeviceResponse])
async def list_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FavoriteDevice)
        .where(FavoriteDevice.user_id == current_user.id)
        .order_by(FavoriteDevice.created_at.desc())
    )
    return [_favorite_response(item) for item in result.scalars().all()]


@router.post("/favorites", response_model=FavoriteDeviceResponse, status_code=201)
async def upsert_favorite(
    data: FavoriteDeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FavoriteDevice).where(
            FavoriteDevice.user_id == current_user.id,
            FavoriteDevice.device_id == data.device_id,
        )
    )
    item = result.scalar_one_or_none()
    if item:
        item.snapshot = data.snapshot
    else:
        item = FavoriteDevice(
            user_id=current_user.id,
            organization_id=await _current_organization_id(db, current_user),
            device_id=data.device_id,
            snapshot=data.snapshot,
        )
        db.add(item)

    await db.commit()
    await db.refresh(item)
    return _favorite_response(item)


@router.delete("/favorites/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_favorite(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FavoriteDevice).where(
            FavoriteDevice.user_id == current_user.id,
            FavoriteDevice.device_id == device_id,
        )
    )
    item = result.scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
    return None


@router.get("/pipeline", response_model=list[DevicePipelineResponse])
async def list_pipeline(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DevicePipeline)
        .where(DevicePipeline.user_id == current_user.id)
        .order_by(DevicePipeline.updated_at.desc().nullslast(), DevicePipeline.created_at.desc())
    )
    return [_pipeline_response(item) for item in result.scalars().all()]


@router.post("/pipeline", response_model=DevicePipelineResponse, status_code=201)
async def upsert_pipeline(
    data: DevicePipelineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DevicePipeline).where(
            DevicePipeline.user_id == current_user.id,
            DevicePipeline.device_id == data.device_id,
        )
    )
    item = result.scalar_one_or_none()
    if item:
        item.pipeline_status = data.pipeline_status
        item.note = data.note
        item.snapshot = data.snapshot
    else:
        await ensure_limit(db, current_user, "pipeline_projects")
        item = DevicePipeline(
            user_id=current_user.id,
            organization_id=await _current_organization_id(db, current_user),
            device_id=data.device_id,
            pipeline_status=data.pipeline_status,
            note=data.note,
            snapshot=data.snapshot,
        )
        db.add(item)

    await db.commit()
    await db.refresh(item)
    return _pipeline_response(item)


@router.delete("/pipeline/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DevicePipeline).where(
            DevicePipeline.user_id == current_user.id,
            DevicePipeline.device_id == device_id,
        )
    )
    item = result.scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
    return None


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(UserPreferences).where(UserPreferences.user_id == current_user.id))
    return _preferences_response(result.scalar_one_or_none())


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_preferences(
    data: UserPreferencesPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(UserPreferences).where(UserPreferences.user_id == current_user.id))
    item = result.scalar_one_or_none()
    if item:
        item.preferences = {**DEFAULT_PREFERENCES, **data.preferences}
    else:
        item = UserPreferences(
            user_id=current_user.id,
            organization_id=await _current_organization_id(db, current_user),
            preferences={**DEFAULT_PREFERENCES, **data.preferences},
        )
        db.add(item)

    await db.commit()
    await db.refresh(item)
    return _preferences_response(item)


@router.get("/match-projects", response_model=list[MatchProjectResponse])
async def list_match_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MatchProject)
        .where(MatchProject.user_id == current_user.id)
        .order_by(MatchProject.updated_at.desc().nullslast(), MatchProject.created_at.desc())
        .limit(10)
    )
    return [_match_response(item) for item in result.scalars().all()]


@router.post("/match-projects", response_model=MatchProjectResponse, status_code=201)
async def create_match_project(
    data: MatchProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = MatchProject(
        user_id=current_user.id,
        organization_id=await _current_organization_id(db, current_user),
        file_name=data.file_name,
        file_size=data.file_size,
        result=data.result,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _match_response(item)
