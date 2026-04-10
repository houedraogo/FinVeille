from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.schemas.source import (
    SourceCreate,
    SourceResponse,
    SourceTestRequest,
    SourceTestResponse,
    SourceUpdate,
)
from app.services.source_service import SourceService

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])


@router.get("/", response_model=List[SourceResponse])
async def list_sources(
    country: Optional[str] = Query(None),
    level: Optional[int] = Query(None),
    active_only: bool = Query(False),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await SourceService(db).get_all(
        country=country,
        level=level,
        active_only=active_only,
        category=category,
    )


@router.get("/stats")
async def source_stats(db: AsyncSession = Depends(get_db)):
    return await SourceService(db).get_stats()


@router.post("/test", response_model=SourceTestResponse)
async def test_source(
    data: SourceTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "editor"])),
):
    return await SourceService(db).test_source(data)


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: UUID, db: AsyncSession = Depends(get_db)):
    source = await SourceService(db).get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source introuvable")
    return source


@router.get("/{source_id}/logs")
async def get_source_logs(source_id: UUID, db: AsyncSession = Depends(get_db)):
    return await SourceService(db).get_logs(source_id)


@router.post("/", response_model=SourceResponse, status_code=201)
async def create_source(
    data: SourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "editor"])),
):
    return await SourceService(db).create(data)


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: UUID,
    data: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "editor"])),
):
    source = await SourceService(db).update(source_id, data)
    if not source:
        raise HTTPException(status_code=404, detail="Source introuvable")
    return source


@router.post("/{source_id}/collect")
async def trigger_collection(
    source_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "editor"])),
):
    """Declenche manuellement la collecte d'une source."""
    source = await SourceService(db).get_model_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source introuvable")

    try:
        from app.tasks.collect_tasks import collect_source

        collect_source.delay(str(source_id))
        return {
            "message": f"Collecte planifiee pour '{source.name}'",
            "source_id": str(source_id),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du declenchement : {e}",
        )


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    await SourceService(db).delete(source_id)
