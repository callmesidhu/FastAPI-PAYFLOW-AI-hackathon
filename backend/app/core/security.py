"""Security and authentication utilities for PAYFLOW AI.

Implements Argon2id password hashing and short-lived JWT generation
using environment-only signing secrets.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import argon2
from argon2.exceptions import VerifyMismatchError, VerificationError
import jwt
from app.core.config import get_settings

settings = get_settings()

# Initialize Argon2id password hasher with secure parameters
_hasher = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=102400,  # 100 MiB
    parallelism=8,
    type=argon2.Type.ID,
)

ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # 12 hours for hackathon MVP


def hash_password(password: str) -> str:
    """Hash plaintext password using modern Argon2id."""
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash with timing safety.

    Returns False if hash is invalid or password does not match.
    """
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError):
        return False
    except Exception:
        return False


def create_access_token(
    subject: str,
    claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT access token using the environment secret key.

    Args:
        subject: The user_id to be stored in the 'sub' claim.
        claims: Optional additional claims to include in payload.
        expires_delta: Optional custom expiration duration.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES))

    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }
    if claims:
        to_encode.update(claims)

    token = jwt.encode(to_encode, settings.APP_SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises:
        jwt.PyJWTError: If signature is invalid, token expired, or malformed.
    """
    return jwt.decode(token, settings.APP_SECRET_KEY, algorithms=[ALGORITHM])
