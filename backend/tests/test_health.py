"""Tests for /health endpoint and basic operational safety."""

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok():
    """Verify /health returns 200 and healthy status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        assert "app" in data
        assert "version" in data
        assert "environment" in data
        assert "database" in data


@pytest.mark.asyncio
async def test_health_does_not_leak_secrets():
    """Verify sensitive environment variables and credentials never leak in health responses."""
    settings = get_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        payload_str = response.text
        data = response.json()

        # Invariant: Secret values should never appear in any response body
        sensitive_values = [
            settings.APP_SECRET_KEY,
            settings.PAYPAL_CLIENT_SECRET,
            settings.MONGODB_URI,
            settings.AI_API_KEY,
        ]
        for secret_val in sensitive_values:
            if secret_val:
                assert secret_val not in payload_str

        # Invariant: Sensitive key names should not be keys in response
        sensitive_key_names = {"secret", "password", "token", "key", "uri", "client_secret"}
        assert not sensitive_key_names.intersection(set(data.keys()))
