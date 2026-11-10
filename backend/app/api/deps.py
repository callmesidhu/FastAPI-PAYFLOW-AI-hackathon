"""FastAPI dependencies for request authentication and user ownership enforcement."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.security import decode_access_token
from app.db.mongodb import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_id

# Enforces Bearer token in Authorization header
bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> User:
    """Dependency that authenticates the caller and returns the verified User entity.

    Invariant:
        Never trusts user_id supplied in query parameters or request bodies.
        The authenticated user_id extracted from the cryptographically verified
        JWT payload is authoritative for all downstream data scoping.
    """
    token = credentials.credentials
    auth_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise auth_exception
    except (jwt.PyJWTError, ValueError):
        raise auth_exception

    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise auth_exception

    return user
