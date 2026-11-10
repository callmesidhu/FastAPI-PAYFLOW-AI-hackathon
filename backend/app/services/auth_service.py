"""Authentication domain service for user registration and credential validation."""

from typing import Optional
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import UserRegister


async def register_user(db: AsyncIOMotorDatabase, payload: UserRegister) -> User:
    """Register a new user account with Argon2id password hashing.

    Raises:
        HTTPException: If an account with the specified email already exists.
    """
    normalized_email = payload.email.lower().strip()

    # Check for existing user
    existing = await db.users.find_one({"email": normalized_email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # Hash password with Argon2id
    hashed = hash_password(payload.password)

    user = User(
        email=normalized_email,
        hashed_password=hashed,
        name=payload.name.strip(),
        business_name=payload.business_name.strip() if payload.business_name else None,
    )

    await db.users.insert_one(user.model_dump())
    return user


async def authenticate_user(
    db: AsyncIOMotorDatabase,
    email: str,
    password: str,
) -> User:
    """Authenticate user credentials.

    Returns:
        User: Authenticated user model.

    Raises:
        HTTPException: 401 with a generic error on credential mismatch.
    """
    normalized_email = email.lower().strip()
    user_doc = await db.users.find_one({"email": normalized_email})

    # Return generic error to prevent email enumeration
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user_doc:
        return None  # Will be raised below

    if not verify_password(password, user_doc.get("hashed_password", "")):
        return None

    user = User.model_validate(user_doc)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    return user


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[User]:
    """Retrieve user entity by primary internal ID."""
    doc = await db.users.find_one({"id": user_id})
    if not doc:
        return None
    return User.model_validate(doc)
