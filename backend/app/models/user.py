"""User entity model."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(BaseModel):
    """User domain model representing an authenticated freelancer/business owner."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    hashed_password: str
    name: str = Field(min_length=1, max_length=120)
    business_name: Optional[str] = Field(default=None, max_length=120)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    is_active: bool = True
