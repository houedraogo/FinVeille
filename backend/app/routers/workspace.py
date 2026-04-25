import uuid as uuid_module
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.organization import Organization, OrganizationMember
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.models.workspace import DevicePipeline, FavoriteDevice, MatchProject, UserPreferences
from app.schemas.workspace import (
    ActivityFeedResponse,
    ActivityItem,
    DevicePipelineCreate,
    DevicePipelineResponse,
    FavoriteDeviceCreate,
    FavoriteDeviceResponse,
    MatchProjectCreate,
    MatchProjectResponse,
    PipelineDocumentAdd,
    SavedSearchCreate,
    SavedSearchResponse,
    SavedSearchUpdate,
    TeamMemberPipelineItem,
    TeamMemberResponse,
    TeamViewResponse,
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
        priority=item.priority or "moyenne",
        reminder_date=item.reminder_date,
        match_project_id=item.match_project_id,
        note=item.note or "",
        documents=item.documents or [],
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
        item.priority = data.priority
        item.reminder_date = data.reminder_date
        item.match_project_id = data.match_project_id
        item.note = data.note
        if data.documents is not None:
            item.documents = data.documents
        item.snapshot = data.snapshot
    else:
        await ensure_limit(db, current_user, "pipeline_projects")
        item = DevicePipeline(
            user_id=current_user.id,
            organization_id=await _current_organization_id(db, current_user),
            device_id=data.device_id,
            pipeline_status=data.pipeline_status,
            priority=data.priority,
            reminder_date=data.reminder_date,
            match_project_id=data.match_project_id,
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


# ─── Documents pipeline ────────────────────────────────────────────────────────

@router.post("/pipeline/{device_id}/documents", response_model=DevicePipelineResponse, status_code=201)
async def add_pipeline_document(
    device_id: UUID,
    data: PipelineDocumentAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attache un document (lien externe ou note) à une candidature pipeline."""
    result = await db.execute(
        select(DevicePipeline).where(
            DevicePipeline.user_id == current_user.id,
            DevicePipeline.device_id == device_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Opportunité non trouvée dans votre pipeline.")

    docs = list(item.documents or [])
    new_doc = {
        "id": str(uuid_module.uuid4()),
        "name": data.name,
        "url": data.url,
        "doc_type": data.doc_type,
        "note": data.note,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    docs.append(new_doc)
    item.documents = docs

    await db.commit()
    await db.refresh(item)
    return _pipeline_response(item)


@router.delete("/pipeline/{device_id}/documents/{doc_id}", response_model=DevicePipelineResponse)
async def remove_pipeline_document(
    device_id: UUID,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supprime un document attaché à une candidature pipeline."""
    result = await db.execute(
        select(DevicePipeline).where(
            DevicePipeline.user_id == current_user.id,
            DevicePipeline.device_id == device_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Opportunité non trouvée dans votre pipeline.")

    item.documents = [d for d in (item.documents or []) if d.get("id") != doc_id]
    await db.commit()
    await db.refresh(item)
    return _pipeline_response(item)


# ─── Vue équipe ────────────────────────────────────────────────────────────────

@router.get("/team", response_model=TeamViewResponse)
async def get_team_view(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne le pipeline de tous les membres de l'organisation de l'utilisateur."""
    org_id = await _current_organization_id(db, current_user)
    if not org_id:
        return TeamViewResponse(organization_id=None, organization_name=None, members=[])

    # Récupérer l'organisation
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalar_one_or_none()

    # Membres actifs de l'org
    members_result = await db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.is_active == True,
        )
        .order_by(OrganizationMember.joined_at.asc())
    )
    members_rows = members_result.all()

    team_members = []
    for membership, user in members_rows:
        # Pipeline de ce membre
        pipeline_result = await db.execute(
            select(DevicePipeline)
            .where(DevicePipeline.user_id == user.id)
            .where(DevicePipeline.pipeline_status.not_in(["non_pertinent", "refuse"]))
            .order_by(DevicePipeline.updated_at.desc().nullslast())
            .limit(20)
        )
        pipeline_items = pipeline_result.scalars().all()

        team_members.append(TeamMemberResponse(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=membership.role,
            pipeline=[
                TeamMemberPipelineItem(
                    device_id=p.device_id,
                    pipeline_status=p.pipeline_status,
                    priority=p.priority or "moyenne",
                    note=p.note or "",
                    documents_count=len(p.documents or []),
                    snapshot=p.snapshot or {},
                    updated_at=p.updated_at,
                )
                for p in pipeline_items
            ],
        ))

    return TeamViewResponse(
        organization_id=org_id,
        organization_name=org.name if org else None,
        members=team_members,
    )


# ─── Historique d'activité ────────────────────────────────────────────────────

@router.get("/activity", response_model=ActivityFeedResponse)
async def get_activity_feed(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 40,
):
    """Flux d'activité unifié : pipeline, favoris, analyses de documents."""
    items: list[ActivityItem] = []

    # ── Pipeline entries ──
    pipeline_result = await db.execute(
        select(DevicePipeline)
        .where(DevicePipeline.user_id == current_user.id)
        .order_by(DevicePipeline.updated_at.desc().nullslast(), DevicePipeline.created_at.desc())
        .limit(limit)
    )
    pipeline_items = pipeline_result.scalars().all()

    PIPELINE_LABELS = {
        "a_etudier": "À étudier",
        "interessant": "Prioritaire",
        "candidature_en_cours": "En cours",
        "soumis": "Soumis",
        "refuse": "Refusé",
        "non_pertinent": "Non pertinent",
    }

    for p in pipeline_items:
        snapshot = p.snapshot or {}
        title = snapshot.get("title", "Opportunité sans titre")
        status_label = PIPELINE_LABELS.get(p.pipeline_status, p.pipeline_status)
        occurred = p.updated_at or p.created_at

        # Entrée principale (changement de statut)
        items.append(ActivityItem(
            id=f"pipeline-{p.device_id}",
            activity_type="pipeline_update",
            label=f"Statut → {status_label}",
            description=f"{title} — passé en « {status_label} »",
            device_id=str(p.device_id),
            device_title=title,
            user_id=str(current_user.id),
            user_name=current_user.full_name or current_user.email,
            occurred_at=occurred,
        ))

        # Documents attachés
        for doc in (p.documents or []):
            try:
                doc_at = datetime.fromisoformat(doc.get("added_at", ""))
            except Exception:
                doc_at = occurred
            items.append(ActivityItem(
                id=f"doc-{doc.get('id', '')}",
                activity_type="document_add",
                label=f"Document · {doc.get('name', 'Sans nom')}",
                description=f"{title} — document ajouté : {doc.get('name', '')}",
                device_id=str(p.device_id),
                device_title=title,
                user_id=str(current_user.id),
                user_name=current_user.full_name or current_user.email,
                occurred_at=doc_at,
            ))

    # ── Favoris ──
    fav_result = await db.execute(
        select(FavoriteDevice)
        .where(FavoriteDevice.user_id == current_user.id)
        .order_by(FavoriteDevice.created_at.desc())
        .limit(20)
    )
    for fav in fav_result.scalars().all():
        snapshot = fav.snapshot or {}
        title = snapshot.get("title", "Opportunité sans titre")
        items.append(ActivityItem(
            id=f"fav-{fav.device_id}",
            activity_type="favorite_add",
            label="Ajouté aux favoris",
            description=f"{title} — ajouté à vos favoris",
            device_id=str(fav.device_id),
            device_title=title,
            user_id=str(current_user.id),
            user_name=current_user.full_name or current_user.email,
            occurred_at=fav.created_at,
        ))

    # ── Match projects ──
    match_result = await db.execute(
        select(MatchProject)
        .where(MatchProject.user_id == current_user.id)
        .order_by(MatchProject.created_at.desc())
        .limit(10)
    )
    for match in match_result.scalars().all():
        total = (match.result or {}).get("total", 0)
        items.append(ActivityItem(
            id=f"match-{match.id}",
            activity_type="match_created",
            label="Analyse de document",
            description=f"Analyse « {match.file_name or 'Document'} » — {total} correspondance(s) trouvée(s)",
            device_id=None,
            device_title=None,
            user_id=str(current_user.id),
            user_name=current_user.full_name or current_user.email,
            occurred_at=match.created_at,
        ))

    # Trier par date desc
    items.sort(key=lambda x: x.occurred_at, reverse=True)
    items = items[:limit]

    return ActivityFeedResponse(items=items, total=len(items))


# ─── Reporting décisionnel ────────────────────────────────────────────────────

@router.get("/reporting")
async def get_pipeline_reporting(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stats pipeline : statuts, taux de soumission/refus, montant cumulé détecté."""
    result = await db.execute(
        select(DevicePipeline).where(DevicePipeline.user_id == current_user.id)
    )
    pipeline_items = result.scalars().all()

    by_status: dict[str, int] = {}
    total_amount = 0.0

    for item in pipeline_items:
        status = item.pipeline_status or "a_etudier"
        by_status[status] = by_status.get(status, 0) + 1
        snapshot = item.snapshot or {}
        amount = snapshot.get("amountMax") or snapshot.get("amount_max") or 0
        try:
            total_amount += float(amount)
        except (TypeError, ValueError):
            pass

    total = len(pipeline_items)
    submitted = by_status.get("soumis", 0)
    refused = by_status.get("refuse", 0)
    non_pertinent = by_status.get("non_pertinent", 0)
    active = total - refused - non_pertinent

    submission_rate = round(submitted / active * 100, 1) if active > 0 else 0.0
    refusal_rate = round(refused / (submitted + refused) * 100, 1) if (submitted + refused) > 0 else 0.0

    # Org team stats if member of an org
    org_id = await _current_organization_id(db, current_user)
    team_stats = None
    if org_id:
        team_result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.is_active == True,
            )
        )
        member_count = len(team_result.scalars().all())

        team_pipeline_result = await db.execute(
            select(DevicePipeline)
            .join(OrganizationMember, OrganizationMember.user_id == DevicePipeline.user_id)
            .where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.is_active == True,
            )
        )
        team_items = team_pipeline_result.scalars().all()
        team_submitted = sum(1 for i in team_items if i.pipeline_status == "soumis")
        team_stats = {
            "member_count": member_count,
            "total_tracked": len(team_items),
            "total_submitted": team_submitted,
        }

    return {
        "total": total,
        "active": active,
        "by_status": by_status,
        "submitted": submitted,
        "refused": refused,
        "non_pertinent": non_pertinent,
        "submission_rate": submission_rate,
        "refusal_rate": refusal_rate,
        "total_amount_detected": total_amount,
        "pipeline_count": total,
        "team_stats": team_stats,
    }
