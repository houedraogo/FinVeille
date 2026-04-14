from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import secrets

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, TokenResponse, LoginRequest, GoogleAuthRequest
from app.utils.auth_utils import hash_password, verify_password, create_access_token
from app.utils.google_auth import verify_google_credential
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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
        role="reader",  # Nouveau compte = lecteur par défaut
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id), user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/google", response_model=TokenResponse)
async def google_auth(data: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    google_user = await verify_google_credential(data.credential)

    existing = await db.execute(
        select(User).where(User.email == google_user["email"], User.is_active == True)
    )
    user = existing.scalar_one_or_none()

    if not user:
        user = User(
            email=google_user["email"],
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name=google_user["full_name"],
            role="reader",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    if not user.full_name and google_user["full_name"]:
        user.full_name = google_user["full_name"]

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    token = create_access_token(str(user.id), user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
