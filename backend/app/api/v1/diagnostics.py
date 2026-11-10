"""Protected diagnostics and operational observability endpoint (Prompt 40).

Enables administrators and evaluators to inspect system health, operational metrics,
and graceful degradation states. Strictly protected by user authentication.
Never exposes credentials, API keys, JWT secrets, or customer PII.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.metrics import metrics_collector
from app.db.mongodb import get_db, get_db_status
from app.models.user import User
from app.services.paypal_service import paypal_service

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics & Observability"])
settings = get_settings()


@router.get(
    "",
    summary="Operational Diagnostics & System Metrics",
    description=(
        "Returns system health, operational error metrics, integration connectivity, "
        "and recovery guidance. Requires authentication. Zero credentials or keys exposed."
    ),
)
async def get_system_diagnostics(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve protected operational health snapshot and telemetry."""
    db_status = await get_db_status()
    paypal_info = await paypal_service.check_connection()

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.APP_ENV,
        "services": {
            "backend": {
                "status": "healthy",
                "app": settings.APP_NAME,
                "version": "0.1.0",
            },
            "database": {
                "status": db_status,
                "database_name": settings.MONGODB_DATABASE,
            },
            "paypal_sandbox": {
                "configured": paypal_info.get("configured", False),
                "connected": paypal_info.get("connected", False),
                "target_host": settings.PAYPAL_BASE_URL,
                "webhook_configured": paypal_info.get("webhook_configured", False),
                "message": paypal_info.get("message", "Operational"),
            },
            "ai_provider": {
                "provider": settings.AI_PROVIDER,
                "model": settings.AI_MODEL,
                "configured": settings.is_ai_configured,
                "fallback_mode": not settings.is_ai_configured,
                "status": "active" if settings.is_ai_configured else "fallback_mock_active",
            },
        },
        "metrics": metrics_collector.get_summary(),
        "recovery_guidance": {
            "ai_unavailable": (
                "If the AI provider is unavailable or rate-limited, manual invoice creation "
                "at /invoices/new remains 100% operational. All database operations and domain logic "
                "function without generative AI."
            ),
            "paypal_unavailable": (
                "If the PayPal Sandbox times out, invoices remain safely stored as local drafts. "
                "The dashboard remains fully functional, displaying current receivables and showing "
                "the PayPal status badge as 'DISCONNECTED'."
            ),
            "webhook_failure": (
                "If webhook delivery is interrupted or unverified, merchants can manually trigger "
                "status reconciliation via Settings -> Sync PayPal Status."
            ),
            "database_interruption": (
                "If the database disconnects, verify network access and MongoDB Atlas IP allowlist. "
                "Endpoints will return safe HTTP 503 Service Unavailable responses without leaking stack traces."
            ),
        },
    }

