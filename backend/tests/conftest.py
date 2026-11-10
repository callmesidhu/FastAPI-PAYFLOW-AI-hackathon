"""Pytest root configuration and shared fixtures for PAYFLOW AI."""

import pytest
from app.core.rate_limit import auth_limiter, ai_limiter
from tests.mock_db import MockDatabase


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Ensure in-memory sliding window rate limiters are clean before each test."""
    auth_limiter.reset()
    ai_limiter.reset()
    yield
    auth_limiter.reset()
    ai_limiter.reset()

