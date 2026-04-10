from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertUpdate, AlertResponse
from app.dependencies import get_current_user
from app.services.alert_service import AlertService

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await AlertService(db).get_user_alerts(current_user.id)


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = await AlertService(db).get_by_id(alert_id)
    if not alert or alert.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    return alert


@router.post("/", response_model=AlertResponse, status_code=201)
async def create_alert(
    data: AlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await AlertService(db).create(data, current_user.id)


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: UUID,
    data: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = await AlertService(db).get_by_id(alert_id)
    if not alert or alert.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    updated = await AlertService(db).update(alert_id, data)
    return updated


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = await AlertService(db).get_by_id(alert_id)
    if not alert or alert.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    await AlertService(db).delete(alert_id)


@router.get("/{alert_id}/preview")
async def preview_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Prévisualise les dispositifs correspondant à une alerte."""
    alert = await AlertService(db).get_by_id(alert_id)
    if not alert or alert.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    devices = await AlertService(db).match_devices(alert)
    return {"count": len(devices), "devices": [
        {"id": str(d.id), "title": d.title, "country": d.country,
         "device_type": d.device_type, "status": d.status}
        for d in devices[:10]
    ]}
