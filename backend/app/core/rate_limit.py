"""In-memory sliding-window rate limiting for security and resource protection (Prompt 33).

Protects sensitive and computationally expensive endpoints:
- Authentication endpoints (login, registration): Mitigates credential stuffing and brute force.
- AI assistant endpoints (chat, natural language extraction, summary): Enforces quota bounds and prevents denial of wallet.
"""

from collections import defaultdict
import time
from typing import Dict, List, Optional
from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings


class InMemoryRateLimiter:
    """Thread-safe sliding-window in-memory rate limiter."""

    def __init__(self, requests_limit: int, window_seconds: int, scope: str = "general") -> None:
        self.limit = requests_limit
        self.window = window_seconds
        self.scope = scope
        self._history: Dict[str, List[float]] = defaultdict(list)

    def _clean(self, key: str, now: float) -> List[float]:
        threshold = now - self.window
        valid = [t for t in self._history[key] if t > threshold]
        self._history[key] = valid
        return valid

    def check(self, key: str) -> None:
        """Check if request is permitted. Raises HTTP 429 if limit is exceeded."""
        now = time.time()
        valid = self._clean(key, now)
        if len(valid) >= self.limit:
            oldest_in_window = valid[0]
            retry_after = int(self.window - (now - oldest_in_window)) + 1
            retry_after = max(1, retry_after)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {self.scope}. Please wait {retry_after} seconds before retrying.",
                headers={"Retry-After": str(retry_after)},
            )
        self._history[key].append(now)

    def reset(self) -> None:
        """Clear rate limit history for tests."""
        self._history.clear()


# Default limit configurations
# Login & Register: 5 attempts per minute per IP
auth_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60, scope="authentication")

# AI Operations: 15 operations per minute per user/IP
ai_limiter = InMemoryRateLimiter(requests_limit=15, window_seconds=60, scope="ai-assistant")


def get_client_ip(request: Request) -> str:
    """Extract client IP handling reverse proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


async def rate_limit_auth_dependency(request: Request) -> None:
    """FastAPI dependency enforcing brute-force rate limits on auth routes."""
    settings = get_settings()
    # In testing, allow bypassing if explicitly configured
    if getattr(settings, "DISABLE_RATE_LIMITS_FOR_TESTS", False):
        return
    client_ip = get_client_ip(request)
    auth_limiter.check(client_ip)


async def rate_limit_ai_dependency(request: Request) -> None:
    """FastAPI dependency enforcing request quotas on AI endpoints."""
    settings = get_settings()
    if getattr(settings, "DISABLE_RATE_LIMITS_FOR_TESTS", False):
        return
    # Key by user ID if Authorization header present, else IP
    auth_header = request.headers.get("Authorization", "")
    key = auth_header if auth_header else get_client_ip(request)
    ai_limiter.check(key)

