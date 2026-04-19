from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operations import AuditLog, EmailEvent


async def record_audit(
    db: AsyncSession,
    action: str,
    user_id: UUID | None = None,
    organization_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            organization_id=organization_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=metadata or {},
        )
    )
    await db.commit()


async def record_email_event(
    db: AsyncSession,
    email: str,
    template: str,
    subject: str,
    status: str,
    user_id: UUID | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        EmailEvent(
            user_id=user_id,
            email=email,
            template=template,
            subject=subject,
            status=status,
            error_message=error_message,
            metadata_json=metadata or {},
        )
    )
    await db.commit()
