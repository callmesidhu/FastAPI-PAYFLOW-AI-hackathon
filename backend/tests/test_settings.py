"""Tests for environment configuration, secrets masking, and CORS rules."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from app.main import app
from app.core.config import Settings, get_settings


def test_default_paypal_base_url_is_official_sandbox():
    """Ensure PayPal base URL defaults to official sandbox host."""
    settings = Settings()
    assert "sandbox.paypal.com" in settings.PAYPAL_BASE_URL
    assert settings.PAYPAL_BASE_URL == "https://api-m.sandbox.paypal.com"


def test_reject_live_paypal_endpoint():
    """Accidental live PayPal endpoints must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(PAYPAL_BASE_URL="https://api.paypal.com")
    assert "Live PayPal endpoint detected" in str(exc_info.value)


def test_missing_settings_produce_actionable_messages():
    """Missing external integration credentials in development must yield actionable messages."""
    settings = Settings(
        APP_ENV="development",
        PAYPAL_CLIENT_ID="",
        PAYPAL_CLIENT_SECRET="",
        AI_API_KEY="",
    )
    messages = settings.get_actionable_startup_messages()
    assert len(messages) >= 2
    assert any("PayPal Sandbox credentials are not fully configured" in msg for msg in messages)
    assert any("AI_API_KEY is not configured" in msg for msg in messages)


def test_production_readiness_validation():
    """Production mode must detect missing secrets and report actionable errors."""
    prod_settings = Settings(
        APP_ENV="production",
        APP_SECRET_KEY="dev-insecure-short",
        PAYPAL_CLIENT_ID="",
        AI_API_KEY="",
        MONGODB_URI="mongodb://localhost:27017",
    )
    missing = prod_settings.validate_production_readiness()
    assert len(missing) >= 3
    assert any("APP_SECRET_KEY" in item for item in missing)
    assert any("PAYPAL_CLIENT_ID" in item for item in missing)
    assert any("AI_API_KEY" in item for item in missing)


def test_cors_wildcard_forbidden_in_production():
    """CORS wildcard '*' must be rejected in production."""
    settings = Settings(
        APP_ENV="production",
        FRONTEND_ORIGIN="*",
    )
    with pytest.raises(ValueError) as exc_info:
        _ = settings.cors_origins
    assert "wildcard '*' is strictly forbidden in production" in str(exc_info.value)


def test_cors_origins_parsing():
    """Multiple origins in FRONTEND_ORIGIN are parsed correctly."""
    settings = Settings(
        FRONTEND_ORIGIN="http://localhost:5173, https://app.payflow.com ",
    )
    origins = settings.cors_origins
    assert origins == ["http://localhost:5173", "https://app.payflow.com"]


def test_settings_repr_masks_secrets():
    """Representation of settings object must mask passwords and secrets."""
    settings = Settings(
        MONGODB_URI="mongodb://admin:secretPassword123@cluster.mongodb.net:27017",
        PAYPAL_CLIENT_SECRET="paypal_super_secret_key",
        APP_SECRET_KEY="app_super_secret_jwt_key",
        AI_API_KEY="gemini_super_secret_ai_key",
    )
    rep = repr(settings)
    assert "secretPassword123" not in rep
    assert "paypal_super_secret_key" not in rep
    assert "app_super_secret_jwt_key" not in rep
    assert "gemini_super_secret_ai_key" not in rep
    assert "admin:***@" in rep


@pytest.mark.asyncio
async def test_secrets_never_exposed_in_health_response():
    """Public health endpoint must never expose secrets or connection strings."""
    settings = get_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        payload_text = response.text
        data = response.json()

        # Values check
        for secret in [settings.APP_SECRET_KEY, settings.PAYPAL_CLIENT_SECRET, settings.AI_API_KEY, settings.MONGODB_URI]:
            if secret:
                assert secret not in payload_text

        # Schema keys check
        forbidden_keys = {"secret", "key", "password", "token", "credentials", "uri"}
        assert not forbidden_keys.intersection(set(data.keys()))
