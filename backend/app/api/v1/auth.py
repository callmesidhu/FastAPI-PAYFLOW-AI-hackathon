"""Authentication endpoints for user registration, login, and current-user identity."""

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.mongodb import get_db
from app.models.user import User
from app.schemas.auth import AuthTokenResponse, UserLogin, UserRegister, UserResponse
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegister,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AuthTokenResponse:
    """Register a new business owner account."""
    user = await register_user(db, payload)
    access_token = create_access_token(subject=user.id)
    return AuthTokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    payload: UserLogin,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AuthTokenResponse:
    """Authenticate with email and password to receive a JWT access token."""
    user = await authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=user.id)
    return AuthTokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Retrieve profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)
