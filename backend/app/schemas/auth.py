"""Authentication request and response schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    """User registration schema with password hygiene."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "owner@payflowstudio.com",
                "password": "SecurePassword123!",
                "name": "Alex Vance",
                "business_name": "Vance Creative Studio",
            }
        }
    )

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100, description="Minimum 8 characters with at least one digit or symbol")
    name: str = Field(..., min_length=1, max_length=120)
    business_name: Optional[str] = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must contain at least 8 characters.")
        if not any(char.isdigit() or not char.isalnum() for char in v):
            raise ValueError("Password must contain at least one number or special character.")
        return v


class UserLogin(BaseModel):
    """User login credential schema."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "owner@payflowstudio.com",
                "password": "SecurePassword123!",
            }
        }
    )

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=100)


class UserResponse(BaseModel):
    """Safe user profile response omitting password hashes."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    name: str
    business_name: Optional[str] = None
    created_at: datetime
    is_active: bool


class AuthTokenResponse(BaseModel):
    """JWT bearer token and authenticated user payload."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
