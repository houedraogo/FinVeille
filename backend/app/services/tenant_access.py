"""Small, fail-closed policy for the active organization and its resources."""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrganizationMember
from app.models.user import User


READ_ROLES = frozenset({"org_owner", "org_admin", "member", "viewer"})
WRITE_ROLES = frozenset({"org_owner", "org_admin", "member"})
MANAGE_ROLES = frozenset({"org_owner", "org_admin"})
BILLING_ROLES = frozenset({"org_owner"})


async def current_membership(db: AsyncSession, user: User) -> OrganizationMember | None:
    result = await db.execute(
        select(OrganizationMember)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.is_active.is_(True),
            Organization.status == "active",
        )
        .order_by(OrganizationMember.joined_at.asc(), OrganizationMember.id.asc())
    )
    memberships = list(result.scalars().all())
    if user.default_organization_id:
        selected = next((item for item in memberships if item.organization_id == user.default_organization_id), None)
    else:
        selected = memberships[0] if memberships else None
    return selected if selected and selected.role in READ_ROLES else None


async def current_organization_id(db: AsyncSession, user: User) -> UUID | None:
    membership = await current_membership(db, user)
    return membership.organization_id if membership and membership.role in READ_ROLES else None


async def require_tenant(db: AsyncSession, user: User, action: str = "read") -> UUID:
    roles = {
        "read": READ_ROLES,
        "write": WRITE_ROLES,
        "export": WRITE_ROLES,
        "manage": MANAGE_ROLES,
        "billing": BILLING_ROLES,
    }
    allowed = roles.get(action)
    if allowed is None:
        raise ValueError(f"Unknown tenant action: {action}")
    membership = await current_membership(db, user)
    if membership is None:
        raise HTTPException(status_code=403, detail="Aucune organisation active autorisée.")
    if membership.role not in allowed:
        raise HTTPException(status_code=403, detail="Rôle insuffisant pour cette opération.")
    return membership.organization_id
