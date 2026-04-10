from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from datetime import date, timedelta, datetime, timezone
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.database import get_db
from app.models.device import Device
from app.models.source import Source
from app.models.user import User as UserModel
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.dependencies import require_role
from app.utils.auth_utils import hash_password
from app.services.device_service import DeviceService
from app.tasks.quality_tasks import build_quality_audit, daily_quality_audit

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# --- Qualité des données ---

@router.get("/quality")
async def quality_report(db: AsyncSession = Depends(get_db),
                          _=Depends(require_role(["admin", "editor"]))):
    """Rapport qualité de la base."""
    today = date.today()

    r = await db.execute(select(func.count()).where(Device.completeness_score < 40))
    incomplete = r.scalar() or 0

    r = await db.execute(select(func.count()).where(Device.close_date < today, Device.status == "open"))
    expired_open = r.scalar() or 0

    r = await db.execute(select(func.count()).where(Device.validation_status == "pending_review"))
    pending = r.scalar() or 0

    r = await db.execute(select(func.count()).where(Device.confidence_score < 30))
    low_confidence = r.scalar() or 0

    r = await db.execute(select(func.avg(Device.completeness_score)))
    avg_completeness = round(float(r.scalar() or 0), 1)

    r = await db.execute(select(func.avg(Device.confidence_score)))
    avg_confidence = round(float(r.scalar() or 0), 1)

    return {
        "incomplete_devices": incomplete,
        "expired_still_open": expired_open,
        "pending_validation": pending,
        "low_confidence": low_confidence,
        "avg_completeness": avg_completeness,
        "avg_confidence": avg_confidence,
    }


@router.post("/quality/fix-expired")
async def fix_expired_devices(db: AsyncSession = Depends(get_db),
                               _=Depends(require_role(["admin"]))):
    """Passe en 'expired' les dispositifs dont la date est dépassée."""
    today = date.today()
    result = await db.execute(
        update(Device)
        .where(and_(Device.close_date < today, Device.status == "open"))
        .values(status="expired", updated_at=datetime.now(timezone.utc))
        .returning(Device.id)
    )
    updated = result.fetchall()
    await db.commit()
    return {"fixed": len(updated), "message": f"{len(updated)} dispositifs passés en 'expired'"}


@router.post("/quality/purge-thin-descriptions")
async def purge_thin_descriptions(
    dry_run: bool = Query(True),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    """Supprime les dispositifs pending_review impossibles Ã  enrichir car trop peu dÃ©crits."""
    return await DeviceService(db).purge_unenrichable_devices(
        actor_id=str(current_user.id),
        limit=limit,
        dry_run=dry_run,
    )


@router.get("/quality/audit")
async def quality_audit(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "editor"])),
):
    """Audit qualité détaillé des dispositifs et des sources récentes."""
    return await build_quality_audit(db)


@router.post("/quality/audit/run")
async def run_quality_audit(_=Depends(require_role(["admin"]))):
    """Déclenche un audit qualité en arrière-plan."""
    daily_quality_audit.delay()
    return {"message": "Audit qualité déclenché en arrière-plan"}


@router.get("/pending")
async def get_pending_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "editor"])),
):
    """Dispositifs en attente de validation."""
    params = __import__("app.schemas.device", fromlist=["DeviceSearchParams"]).DeviceSearchParams(
        validation_status="pending_review", page=page, page_size=page_size
    )
    return await DeviceService(db).search(params)


# --- Gestion utilisateurs ---

@router.get("/users", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db),
                     _=Depends(require_role(["admin"]))):
    result = await db.execute(select(UserModel).order_by(UserModel.created_at.desc()))
    return result.scalars().all()


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db),
                       _=Depends(require_role(["admin"]))):
    from sqlalchemy import select as sel
    existing = await db.execute(sel(UserModel).where(UserModel.email == data.email))
    if existing.scalar_one_or_none():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    user = UserModel(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: UUID, data: UserUpdate,
                       db: AsyncSession = Depends(get_db),
                       _=Depends(require_role(["admin"]))):
    from fastapi import HTTPException
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    return user


# --- Collecte ---

@router.post("/collect/all")
async def collect_all_sources(_=Depends(require_role(["admin"]))):
    """Déclenche la collecte de toutes les sources actives."""
    try:
        from app.tasks.collect_tasks import collect_all_active
        collect_all_active.delay()
        return {"message": "Collecte globale déclenchée"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enrich")
async def enrich_devices(
    batch_size: int = Query(50, ge=1, le=200),
    _=Depends(require_role(["admin"])),
):
    """Déclenche l'enrichissement des fiches incomplètes (scraping source_url)."""
    try:
        from app.tasks.quality_tasks import enrich_missing_fields
        enrich_missing_fields.delay(batch_size=batch_size)
        return {"message": f"Enrichissement de {batch_size} fiches déclenché en arrière-plan"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


# --- Déduplication ---

@router.get("/dedup")
async def get_duplicates(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "editor"])),
):
    """Détecte les groupes de doublons dans la base."""
    from app.services.dedup_service import DedupService
    return await DedupService(db).find_duplicate_groups()


class MergeGroupRequest(BaseModel):
    canonical_id: str
    duplicate_ids: List[str]


@router.post("/dedup/merge")
async def merge_duplicates_auto(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
):
    """Fusionne automatiquement tous les doublons détectés."""
    from app.services.dedup_service import DedupService
    return await DedupService(db).merge_duplicates_auto()


@router.post("/dedup/merge-group")
async def merge_group(
    body: MergeGroupRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
):
    """Fusionne manuellement un groupe de doublons."""
    from app.services.dedup_service import DedupService
    try:
        return await DedupService(db).merge_group(body.canonical_id, body.duplicate_ids)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Email ---

@router.get("/email/status")
async def email_status(_=Depends(require_role(["admin"]))):
    """Vérifie la configuration et la joignabilité du serveur SMTP."""
    from app.services.notification_service import NotificationService
    return NotificationService.smtp_status()


@router.post("/email/test")
async def send_test_email(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    """Envoie un email de test à l'administrateur connecté."""
    from app.services.notification_service import NotificationService
    from fastapi import HTTPException

    status = NotificationService.smtp_status()
    if not status["reachable"]:
        raise HTTPException(
            status_code=503,
            detail=f"SMTP non joignable : {status['message']}"
        )

    html = NotificationService.build_alert_email(
        user_name=current_user.full_name or current_user.email,
        devices=[],
        alert_name="Test de configuration",
    )
    # Remplacer le corps vide par un message de test
    html = html.replace(
        "0 dispositif(s) correspondent à votre veille <strong>Test de configuration</strong>",
        "Ceci est un email de test. Si vous le recevez, votre configuration SMTP fonctionne correctement.",
    )

    ok = NotificationService.send_email(
        to=current_user.email,
        subject="[FinVeille] Test de configuration email",
        html_body=html,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Échec de l'envoi. Vérifiez les logs du backend.")

    return {"sent": True, "to": current_user.email, "message": f"Email de test envoyé à {current_user.email}"}
