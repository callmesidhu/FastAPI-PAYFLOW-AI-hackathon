"""Typed configuration settings for PAYFLOW AI using pydantic-settings.

Enforces zero-secret exposure, safe defaults for local development/tests,
and strict validation for production deployments.
"""

from functools import lru_cache
from typing import Any, Dict, List, Optional
import re
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration schema with validation and secret masking."""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application
    APP_ENV: str = Field(default="development", description="Runtime environment: development, test, or production")
    APP_NAME: str = Field(default="PAYFLOW AI", description="Application display name")
    APP_SECRET_KEY: str = Field(
        default="dev-insecure-secret-key-change-in-production-min-32-chars",
        description="JWT signing key and cryptographic salt. Must be >= 32 characters in production.",
    )
    PORT: int = Field(default=8000, description="Server port")
    FRONTEND_ORIGIN: str = Field(
        default="http://localhost:5173",
        description="Comma-separated allowed origins for CORS (e.g. http://localhost:5173,https://payflow.onrender.com)",
    )

    # Database
    MONGODB_URI: str = Field(default="mongodb://localhost:27017", description="MongoDB connection URI")
    MONGODB_DATABASE: str = Field(default="payflow_ai", description="MongoDB database name")

    # PayPal REST API (Sandbox Default)
    # MUST default to the official Sandbox API host: https://api-m.sandbox.paypal.com
    PAYPAL_BASE_URL: str = Field(
        default="https://api-m.sandbox.paypal.com",
        description="PayPal REST API base URL. Must default to sandbox, never live.",
    )
    PAYPAL_CLIENT_ID: str = Field(default="", description="PayPal REST API client ID")
    PAYPAL_CLIENT_SECRET: str = Field(default="", description="PayPal REST API client secret")
    PAYPAL_WEBHOOK_ID: str = Field(default="", description="Configured PayPal webhook identifier")

    # AI Provider
    AI_PROVIDER: str = Field(default="gemini", description="AI provider: gemini, openai, or mock")
    AI_API_KEY: str = Field(default="", description="API key for the AI provider")
    AI_MODEL: str = Field(default="gemini-2.5-flash", description="AI model identifier")

    # Optional Email & Automation
    EMAIL_PROVIDER: Optional[str] = Field(default=None, description="Optional transactional email provider")
    ZAPIER_WEBHOOK_URL: Optional[str] = Field(default=None, description="Optional Zapier webhook endpoint")
    ZAPIER_SHARED_SECRET: Optional[str] = Field(default=None, description="Optional shared secret for signing Zapier webhooks")

    # Security & Rate Limiting (Prompt 33)
    DISABLE_RATE_LIMITS_FOR_TESTS: bool = Field(
        default=False,
        description="Whether to disable sliding-window rate limit checks during automated tests.",
    )

    @field_validator("PAYPAL_BASE_URL")
    @classmethod
    def validate_paypal_base_url(cls, v: str) -> str:
        """Enforce standard PayPal endpoints and normalize trailing slashes."""
        cleaned = v.rstrip("/")
        if "api.paypal.com" in cleaned and "sandbox" not in cleaned:
            # We explicitly prevent accidental live PayPal host in hackathon setting
            raise ValueError(
                "Live PayPal endpoint detected! PAYFLOW AI requires official PayPal Sandbox "
                "(https://api-m.sandbox.paypal.com) for the hackathon."
            )
        return cleaned

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.APP_ENV.lower() == "production"

    @property
    def is_paypal_configured(self) -> bool:
        """Verify whether PayPal credentials are non-empty and non-placeholder."""
        return bool(
            self.PAYPAL_CLIENT_ID
            and self.PAYPAL_CLIENT_SECRET
            and "placeholder" not in self.PAYPAL_CLIENT_ID.lower()
            and "placeholder" not in self.PAYPAL_CLIENT_SECRET.lower()
        )

    @property
    def is_ai_configured(self) -> bool:
        """Verify whether AI provider API key is provided."""
        return bool(
            self.AI_API_KEY
            and "placeholder" not in self.AI_API_KEY.lower()
            and "your_" not in self.AI_API_KEY.lower()
        )

    @property
    def cors_origins(self) -> List[str]:
        """Parsed list of allowed CORS origins."""
        origins = [origin.strip() for origin in self.FRONTEND_ORIGIN.split(",") if origin.strip()]
        if self.is_production and "*" in origins:
            raise ValueError("CORS wildcard '*' is strictly forbidden in production mode.")
        return origins

    def validate_production_readiness(self) -> List[str]:
        """Validate production configuration and return missing requirements."""
        missing = []
        if self.is_production:
            if not self.APP_SECRET_KEY or len(self.APP_SECRET_KEY) < 32 or "dev-insecure" in self.APP_SECRET_KEY:
                missing.append("APP_SECRET_KEY must be a cryptographically random secret of at least 32 characters.")
            if not self.is_paypal_configured:
                missing.append("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be configured for PayPal Sandbox.")
            if not self.is_ai_configured:
                missing.append("AI_API_KEY must be set for the configured AI_PROVIDER.")
            if not self.MONGODB_URI or "localhost" in self.MONGODB_URI:
                missing.append("MONGODB_URI must point to a production-accessible cluster (e.g., MongoDB Atlas).")
        return missing

    def get_actionable_startup_messages(self) -> List[str]:
        """Generate human-readable diagnostic messages regarding active configurations."""
        messages: List[str] = []

        if not self.is_paypal_configured:
            messages.append(
                "NOTICE: PayPal Sandbox credentials are not fully configured. "
                "PayPal API operations will run in local mock/diagnostic mode. "
                "To connect: set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET."
            )
        else:
            messages.append("PayPal Sandbox integration: CONFIGURED (endpoint: " + self.PAYPAL_BASE_URL + ")")

        if not self.is_ai_configured:
            messages.append(
                f"NOTICE: AI_API_KEY is not configured for provider '{self.AI_PROVIDER}'. "
                "AI assistant calls will use local fallback/mock intent parser. "
                "To connect: set AI_API_KEY."
            )
        else:
            messages.append(f"AI Assistant provider: CONFIGURED ({self.AI_PROVIDER} / {self.AI_MODEL})")

        return messages

    def __repr__(self) -> str:
        """Safe representation masking all credentials."""
        masked_uri = re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", self.MONGODB_URI)
        return (
            f"<Settings app={self.APP_NAME} env={self.APP_ENV} "
            f"paypal_configured={self.is_paypal_configured} "
            f"ai_configured={self.is_ai_configured} "
            f"mongodb={masked_uri}>"
        )

    def __str__(self) -> str:
        return self.__repr__()


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
