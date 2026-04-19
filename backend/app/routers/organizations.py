import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, is_platform_super_admin
from app.models.organization import Invitation, Organization, OrganizationMember
from app.models.user import User
from app.config import settings
from app.services.audit_service import record_audit, record_email_event
from app.services.billing_service import ensure_limit
from app.services.notification_service import NotificationService
from app.schemas.organization import (
    InvitationResponse,
    MeContextResponse,
    OrganizationCreate,
    OrganizationInvitationCreate,
    OrganizationMemberResponse,
    OrganizationResponse,
)

router = APIRouter(prefix="/api/v1", tags=["organizations"])

ORG_ADMIN_ROLES = {"org_owner", "org_admin"}
ORG_MEMBER_ROLES = {"org_owner", "org_admin", "member", "viewer"}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or f"org-{secrets.token_hex(4)}"


async def _unique_slug(db: AsyncSession, name: str) -> str:
    base = _slugify(name)
    slug = base
    index = 2
    while True:
        result = await db.execute(select(Organization.id).where(Organization.slug == slug))
        if not result.scalar_one_or_none():
            return slug
        slug = f"{base}-{index}"
        index += 1


async def _memberships(db: AsyncSession, user_id: UUID) -> list[OrganizationMember]:
    result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user_id, OrganizationMember.is_active == True)
        .order_by(OrganizationMember.joined_at.asc())
    )
    return list(result.scalars().all())


async def _current_membership(db: AsyncSession, user: User) -> OrganizationMember | None:
    memberships = await _memberships(db, user.id)
    if not memberships:
        return None
    if user.default_organization_id:
        for membership in memberships:
            if membership.organization_id == user.default_organization_id:
                return membership
    return memberships[0]


async def _get_current_organization(db: AsyncSession, user: User) -> tuple[Organization | None, OrganizationMember | None]:
    membership = await _current_membership(db, user)
    if not membership:
        return None, None
    result = await db.execute(select(Organization).where(Organization.id == membership.organization_id))
    return result.scalar_one_or_none(), membership


def _permissions(user: User, membership: OrganizationMember | None) -> dict[str, bool]:
    is_super = is_platform_super_admin(user)
    org_role = membership.role if membership else None
    is_org_admin = org_role in ORG_ADMIN_ROLES

    return {
        "can_access_platform_admin": is_super,
        "can_manage_billing": is_super or org_role == "org_owner",
        "can_invite_users": is_super or is_org_admin,
        "can_manage_workspace": bool(membership) or is_super,
        "can_export": org_role in {"org_owner", "org_admin", "member"} or is_super,
        "can_use_matching": org_role in {"org_owner", "org_admin", "member"} or is_super,
        "can_manage_sources": user.role in {"admin", "editor"} or is_super,
    }


@router.get("/me/context", response_model=MeContextResponse)
async def get_me_context(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, membership = await _get_current_organization(db, current_user)
    memberships = await _memberships(db, current_user.id)
    return {
        "user": current_user,
        "current_organization": org,
        "memberships": memberships,
        "permissions": _permissions(current_user, membership),
    }


@router.get("/organizations/current", response_model=OrganizationResponse)
async def get_current_organization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, _membership = await _get_current_organization(db, current_user)
    if not org:
        raise HTTPException(status_code=404, detail="Aucune organisation active pour cet utilisateur.")
    return org


@router.post("/organizations", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    slug = await _unique_slug(db, data.name)
    organization = Organization(name=data.name.strip(), slug=slug, created_by_id=current_user.id)
    db.add(organization)
    await db.flush()

    membership = OrganizationMember(
        organization_id=organization.id,
        user_id=current_user.id,
        role="org_owner",
    )
    db.add(membership)

    if not current_user.default_organization_id:
        current_user.default_organization_id = organization.id

    await db.commit()
    await db.refresh(organization)
    return organization


@router.post("/organizations/invite", response_model=InvitationResponse, status_code=201)
async def invite_to_organization(
    data: OrganizationInvitationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.role not in {"org_admin", "member", "viewer"}:
        raise HTTPException(status_code=422, detail="Rôle d'organisation invalide.")

    current_org, current_membership = await _get_current_organization(db, current_user)
    organization_id = data.organization_id or (current_org.id if current_org else None)
    if not organization_id:
        raise HTTPException(status_code=404, detail="Aucune organisation disponible pour l'invitation.")

    if not is_platform_super_admin(current_user):
        if not current_membership or current_membership.organization_id != organization_id or current_membership.role not in ORG_ADMIN_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invitation réservée aux administrateurs de l'organisation.")

    await ensure_limit(db, current_user, "users")

    invitation = Invitation(
        organization_id=organization_id,
        email=data.email.lower(),
        role=data.role,
        token=secrets.token_urlsafe(32),
        invited_by_id=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    invite_url = f"{settings.PUBLIC_APP_URL}/settings/team?invitation_token={invitation.token}"
    sent = NotificationService.send_email(
        invitation.email,
        "Invitation a rejoindre FinVeille",
        f"<p>Bonjour,</p><p>Vous avez ete invite a rejoindre une organisation FinVeille.</p><p><a href='{invite_url}'>{invite_url}</a></p>",
    )
    await record_email_event(
        db,
        email=invitation.email,
        template="organization_invitation",
        subject="Invitation a rejoindre FinVeille",
        status="sent" if sent else "skipped",
        user_id=current_user.id,
        metadata={"invitation_id": str(invitation.id)},
    )
    await record_audit(
        db,
        action="organization_invitation_created",
        user_id=current_user.id,
        organization_id=invitation.organization_id,
        resource_type="invitation",
        resource_id=str(invitation.id),
    )
    return invitation


@router.post("/organizations/invitations/{token}/accept", response_model=OrganizationMemberResponse)
async def accept_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation introuvable.")
    if invitation.accepted_at:
        raise HTTPException(status_code=400, detail="Invitation déjà acceptée.")
    if invitation.expires_at and invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invitation expirée.")
    if invitation.email.lower() != current_user.email.lower():
        raise HTTPException(status_code=403, detail="Cette invitation ne correspond pas à votre email.")

    existing = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == invitation.organization_id,
            OrganizationMember.user_id == current_user.id,
        )
    )
    membership = existing.scalar_one_or_none()
    if not membership:
        membership = OrganizationMember(
            organization_id=invitation.organization_id,
            user_id=current_user.id,
            role=invitation.role,
        )
        db.add(membership)
    else:
        membership.role = invitation.role
        membership.is_active = True

    invitation.accepted_at = datetime.now(timezone.utc)
    if not current_user.default_organization_id:
        current_user.default_organization_id = invitation.organization_id

    await db.commit()
    await db.refresh(membership)
    return membership
