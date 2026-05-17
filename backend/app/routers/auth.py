from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import re
import secrets

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from app.models.billing import Plan, Subscription
from app.schemas.user import UserCreate, UserResponse, TokenResponse, LoginRequest, GoogleAuthRequest
from app.utils.auth_utils import hash_password, verify_password, create_access_token
from app.utils.google_auth import verify_google_credential
from app.dependencies import get_current_user
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _make_slug(base: str, suffix: str = "") -> str:
    """Génère un slug URL-safe depuis une chaîne."""
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    slug = slug[:40]
    if suffix:
        slug = f"{slug}-{suffix}"
    return slug or "org"


async def _create_personal_org(db: AsyncSession, user: User) -> Organization:
    """
    Crée une organisation personnelle pour un nouvel utilisateur et l'y ajoute
    comme org_owner. Attache également une subscription free si le plan existe.
    """
    # Choisir le nom : prénom ou email local part
    base_name = user.full_name or user.email.split("@")[0]
    org_name = base_name.strip() or "Mon organisation"

    # Générer un slug unique
    base_slug = _make_slug(base_name)
    slug = base_slug
    counter = 1
    while True:
        existing = await db.execute(select(Organization.id).where(Organization.slug == slug))
        if not existing.scalar_one_or_none():
            break
        slug = _make_slug(base_slug, str(counter))
        counter += 1

    # Créer l'organisation
    org = Organization(
        name=org_name,
        slug=slug,
        plan="free",
        status="active",
        created_by_id=user.id,
    )
    db.add(org)
    await db.flush()  # pour récupérer org.id avant commit

    # Ajouter l'utilisateur comme propriétaire
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="org_owner",
        is_active=True,
    )
    db.add(member)

    # Attacher la subscription free si le plan existe
    free_plan = (await db.execute(select(Plan).where(Plan.slug == "free"))).scalar_one_or_none()
    if free_plan:
        subscription = Subscription(
            organization_id=org.id,
            plan_id=free_plan.id,
            status="active",
        )
        db.add(subscription)

    # Lier l'utilisateur à son organisation par défaut
    user.default_organization_id = org.id
    await db.commit()
    await db.refresh(org)
    return org


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.email == data.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    token = create_access_token(str(user.id), user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role="reader",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Créer automatiquement une organisation personnelle
    await _create_personal_org(db, user)
    await db.refresh(user)

    # Notifier l'admin
    try:
        NotificationService.notify_admin_new_user(
            user_email=user.email,
            user_name=user.full_name or "",
            method="email",
        )
    except Exception:
        pass

    token = create_access_token(str(user.id), user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/google", response_model=TokenResponse)
async def google_auth(data: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    google_user = await verify_google_credential(data.credential)

    existing = await db.execute(
        select(User).where(User.email == google_user["email"], User.is_active == True)
    )
    user = existing.scalar_one_or_none()
    is_new = user is None

    if is_new:
        user = User(
            email=google_user["email"],
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name=google_user["full_name"],
            role="reader",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Notifier l'admin
        try:
            NotificationService.notify_admin_new_user(
                user_email=user.email,
                user_name=user.full_name or "",
                method="google",
            )
        except Exception:
            pass

    if not user.full_name and google_user["full_name"]:
        user.full_name = google_user["full_name"]

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Créer une organisation si l'utilisateur n'en a pas encore
    if not user.default_organization_id:
        has_org = (await db.execute(
            select(OrganizationMember.id).where(OrganizationMember.user_id == user.id)
        )).scalar_one_or_none()
        if not has_org:
            await _create_personal_org(db, user)
            await db.refresh(user)

    token = create_access_token(str(user.id), user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
