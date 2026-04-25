from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.device import Device
from app.models.relevance import FundingProject, OrganizationProfile
from app.models.user import User
from app.schemas.device import DeviceSearchParams
from app.schemas.relevance import (
    DeviceRelevanceResponse,
    FundingProjectCreate,
    FundingProjectResponse,
    FundingProjectUpdate,
    OrganizationProfilePayload,
    OrganizationProfileResponse,
    RecommendationItem,
    RecommendationListResponse,
)
from app.services.device_service import DeviceService
from app.services.opportunity_relevance_service import OpportunityRelevanceService

router = APIRouter(prefix="/api/v1", tags=["relevance"])


@router.get("/me/profile", response_model=OrganizationProfileResponse | None)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = OpportunityRelevanceService(db)
    organization_id = await service.get_current_organization_id(current_user)
    if not organization_id:
        return None
    return await service.get_profile(organization_id)


@router.put("/me/profile", response_model=OrganizationProfileResponse)
async def upsert_my_profile(
    payload: OrganizationProfilePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = OpportunityRelevanceService(db)
    organization_id = await service.get_current_organization_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=404, detail="Aucune organisation active pour cet utilisateur.")

    result = await db.execute(
        select(OrganizationProfile).where(OrganizationProfile.organization_id == organization_id)
    )
    profile = result.scalar_one_or_none()
    data = payload.model_dump()
    if profile:
        for key, value in data.items():
            setattr(profile, key, value)
    else:
        profile = OrganizationProfile(organization_id=organization_id, **data)
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/funding-projects", response_model=list[FundingProjectResponse])
async def list_funding_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = OpportunityRelevanceService(db)
    organization_id = await service.get_current_organization_id(current_user)
    if not organization_id:
        return []
    result = await db.execute(
        select(FundingProject)
        .where(FundingProject.organization_id == organization_id)
        .order_by(FundingProject.is_primary.desc(), FundingProject.updated_at.desc())
    )
    return list(result.scalars().all())


@router.post("/funding-projects", response_model=FundingProjectResponse, status_code=201)
async def create_funding_project(
    payload: FundingProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = OpportunityRelevanceService(db)
    organization_id = await service.get_current_organization_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=404, detail="Aucune organisation active pour cet utilisateur.")

    if payload.is_primary:
        existing_primary = await db.execute(
            select(FundingProject).where(FundingProject.organization_id == organization_id, FundingProject.is_primary == True)
        )
        for item in existing_primary.scalars().all():
            item.is_primary = False

    project = FundingProject(
        organization_id=organization_id,
        created_by_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.put("/funding-projects/{project_id}", response_model=FundingProjectResponse)
async def update_funding_project(
    project_id: UUID,
    payload: FundingProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = OpportunityRelevanceService(db)
    organization_id = await service.get_current_organization_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=404, detail="Aucune organisation active pour cet utilisateur.")

    result = await db.execute(
        select(FundingProject).where(FundingProject.id == project_id, FundingProject.organization_id == organization_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Projet de financement introuvable.")

    data = payload.model_dump(exclude_unset=True)
    if data.get("is_primary"):
        previous = await db.execute(
            select(FundingProject).where(FundingProject.organization_id == organization_id, FundingProject.is_primary == True)
        )
        for item in previous.scalars().all():
            item.is_primary = False

    for key, value in data.items():
        setattr(project, key, value)

    await service.clear_project_cache(organization_id, project.id)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/funding-projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_funding_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = OpportunityRelevanceService(db)
    organization_id = await service.get_current_organization_id(current_user)
    if not organization_id:
        return None
    result = await db.execute(
        select(FundingProject).where(FundingProject.id == project_id, FundingProject.organization_id == organization_id)
    )
    project = result.scalar_one_or_none()
    if project:
        await service.clear_project_cache(organization_id, project.id)
        await db.delete(project)
        await db.commit()
    return None


@router.get("/recommendations", response_model=RecommendationListResponse)
async def get_recommendations(
    project_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    relevance_service = OpportunityRelevanceService(db)
    organization_id = await relevance_service.get_current_organization_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=404, detail="Aucune organisation active pour cet utilisateur.")

    profile = await relevance_service.get_profile(organization_id)
    project = await relevance_service.get_project(organization_id, project_id)
    if not profile and not project:
        raise HTTPException(
            status_code=400,
            detail="Complétez d'abord votre profil organisation ou créez un projet de financement.",
        )

    params = DeviceSearchParams(
        countries=project.countries if project and project.countries else (profile.countries if profile else None),
        device_types=project.target_funding_types if project and project.target_funding_types else (profile.target_funding_types if profile else None),
        sectors=project.sectors if project and project.sectors else (profile.sectors if profile else None),
        beneficiaries=project.beneficiaries if project and project.beneficiaries else None,
        status=["open", "recurring", "standby"],
        sort_by="relevance",
        page=page,
        page_size=page_size,
    )
    result = await DeviceService(db).search(params)
    items = list(result["items"])
    relevance_results = await relevance_service.evaluate_devices(items, user=current_user, project_id=project_id)
    by_device = {value.device_id: value for value in relevance_results}
    ordered = sorted(items, key=lambda item: by_device.get(item.id).relevance_score if by_device.get(item.id) else 0, reverse=True)

    for item in ordered:
        relevance = by_device.get(item.id)
        if relevance:
            item.relevance_score = relevance.relevance_score
            item.relevance_label = relevance.relevance_label
            item.relevance_reasons = relevance.reason_texts
            item.priority_level = relevance.priority_level
            item.eligibility_confidence = relevance.eligibility_confidence
            item.decision_hint = relevance.decision_hint
            item.match_reasons = relevance.reason_texts[:3]

    recommendation_items = [
        RecommendationItem(device=item, relevance=DeviceRelevanceResponse(**by_device[item.id].__dict__))
        for item in ordered
        if item.id in by_device
    ]
    return RecommendationListResponse(
        items=recommendation_items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        pages=result["pages"],
    )


@router.post("/recommendations/refresh", response_model=list[DeviceRelevanceResponse])
async def refresh_recommendations(
    project_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = OpportunityRelevanceService(db)
    organization_id = await service.get_current_organization_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=404, detail="Aucune organisation active pour cet utilisateur.")

    profile = await service.get_profile(organization_id)
    project = await service.get_project(organization_id, project_id)
    params = DeviceSearchParams(
        countries=project.countries if project and project.countries else (profile.countries if profile else None),
        device_types=project.target_funding_types if project and project.target_funding_types else (profile.target_funding_types if profile else None),
        sectors=project.sectors if project and project.sectors else (profile.sectors if profile else None),
        beneficiaries=project.beneficiaries if project and project.beneficiaries else None,
        status=["open", "recurring", "standby"],
        sort_by="updated_at",
        page=1,
        page_size=limit,
    )
    result = await DeviceService(db).search(params)
    caches = await service.refresh_cache_for_scope(user=current_user, devices=result["items"], project_id=project_id)
    return [
        DeviceRelevanceResponse(
            device_id=cache.device_id,
            organization_id=cache.organization_id,
            funding_project_id=cache.funding_project_id,
            relevance_score=cache.relevance_score,
            relevance_label=cache.relevance_label or "",
            priority_level=cache.priority_level or "moyenne",
            eligibility_confidence=cache.eligibility_confidence or "à confirmer",
            decision_hint=cache.decision_hint or "",
            reason_codes=list(cache.reason_codes or []),
            reason_texts=list(cache.reason_texts or []),
            computed_at=cache.computed_at,
        )
        for cache in caches
    ]


@router.get("/devices/{device_id}/relevance", response_model=DeviceRelevanceResponse)
async def get_device_relevance(
    device_id: UUID,
    project_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = await DeviceService(db).get_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Opportunité introuvable.")

    service = OpportunityRelevanceService(db)
    results = await service.evaluate_devices([device], user=current_user, project_id=project_id)
    if not results:
        raise HTTPException(status_code=404, detail="Aucune organisation active pour cet utilisateur.")
    result = results[0]
    return DeviceRelevanceResponse(**result.__dict__)


@router.post("/devices/{device_id}/relevance", response_model=DeviceRelevanceResponse)
async def refresh_device_relevance(
    device_id: UUID,
    project_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = await DeviceService(db).get_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Opportunité introuvable.")

    service = OpportunityRelevanceService(db)
    results = await service.evaluate_devices([device], user=current_user, project_id=project_id)
    if not results:
        raise HTTPException(status_code=404, detail="Aucune organisation active pour cet utilisateur.")
    result = results[0]
    await service.save_cache(result)
    await db.commit()
    return DeviceRelevanceResponse(**result.__dict__)
