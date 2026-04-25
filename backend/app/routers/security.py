import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_platform_role
from app.models.operations import AuditLog, DataExport, DeletionRequest, PasswordResetToken
from app.models.user import User
from app.schemas.security import (
    AuditLogResponse,
    DataExportResponse,
    DeletionRequestCreate,
    DeletionRequestResponse,
    PasswordForgotRequest,
    PasswordResetRequest,
)
from app.services.audit_service import record_audit, record_email_event
from app.services.notification_service import NotificationService
from app.utils.auth_utils import hash_password

router = APIRouter(prefix="/api/v1/security", tags=["security"])


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("/password/forgot")
async def forgot_password(
    data: PasswordForgotRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email.lower(), User.is_active == True))
    user = result.scalar_one_or_none()
    if user:
        token = secrets.token_urlsafe(48)
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        db.add(reset)
        await db.commit()

        reset_url = f"{settings.PUBLIC_APP_URL}/settings/security?reset_token={token}"
        sent = NotificationService.send_email(
            user.email,
            "Reinitialisation de votre mot de passe Kafundo",
            f"<p>Bonjour,</p><p>Pour reinitialiser votre mot de passe, ouvrez ce lien :</p><p><a href='{reset_url}'>{reset_url}</a></p>",
        )
        await record_email_event(
            db,
            email=user.email,
            template="password_reset",
            subject="Reinitialisation de votre mot de passe Kafundo",
            status="sent" if sent else "skipped",
            user_id=user.id,
        )
        await record_audit(
            db,
            action="password_reset_requested",
            user_id=user.id,
            ip_address=request.client.host if request.client else None,
        )

    return {"message": "Si ce compte existe, un email de reinitialisation a ete envoye."}


@router.post("/password/reset")
async def reset_password(
    data: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(data.token)))
    reset = result.scalar_one_or_none()
    if not reset or reset.used_at or reset.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Lien de reinitialisation invalide ou expire.")

    user_result = await db.execute(select(User).where(User.id == reset.user_id, User.is_active == True))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    user.password_hash = hash_password(data.new_password)
    reset.used_at = datetime.now(timezone.utc)
    await db.commit()
    await record_audit(
        db,
        action="password_reset_completed",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    return {"message": "Mot de passe mis a jour."}


@router.post("/data-export", response_model=DataExportResponse, status_code=201)
async def create_data_export(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = {
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        }
    }
    data_export = DataExport(
        user_id=current_user.id,
        download_token=secrets.token_urlsafe(32),
        payload=payload,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(data_export)
    await db.commit()
    await db.refresh(data_export)
    await record_audit(db, action="data_export_created", user_id=current_user.id, resource_type="data_export", resource_id=str(data_export.id))
    return data_export


@router.post("/deletion-request", response_model=DeletionRequestResponse, status_code=201)
async def create_deletion_request(
    data: DeletionRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deletion = DeletionRequest(
        user_id=current_user.id,
        reason=data.reason,
        scheduled_for=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(deletion)
    await db.commit()
    await db.refresh(deletion)
    await record_audit(db, action="deletion_request_created", user_id=current_user.id, resource_type="deletion_request", resource_id=str(deletion.id))
    return deletion


@router.get("/admin/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_platform_role(["super_admin"])),
):
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))
    return list(result.scalars().all())
