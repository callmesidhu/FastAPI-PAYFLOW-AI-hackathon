"""PayPal Webhook Receiver API router (Prompt 23).

Handles asynchronous notifications from PayPal Developer Sandbox:
- Cryptographic signature verification via official endpoint (/v1/notifications/verify-webhook-signature).
- Rejection of unverified or tampered payloads (HTTP 400 / 401).
- Idempotency & replay protection via unique event_id persistence.
- Safe ledger reconciliation and state transitions.
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import get_db
from app.schemas.webhook import WebhookProcessingResponse
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/paypal",
    response_model=WebhookProcessingResponse,
    status_code=status.HTTP_200_OK,
    summary="PayPal Webhook Ingestion & State Reconciliation",
    description=(
        "Ingests official PayPal webhook notifications. "
        "Cryptographically verifies webhook signature with PayPal API. "
        "Rejects unverified payloads with HTTP 400/401. "
        "Persists verified events and applies idempotent state transitions and transaction records."
    ),
)
async def paypal_webhook_handler(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> WebhookProcessingResponse:
    """Receive and verify an incoming PayPal webhook notification."""
    try:
        raw_body: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload in webhook request.",
        )

    # Normalize request headers as a standard string dict
    headers = {k: v for k, v in request.headers.items()}

    return await WebhookService.process_webhook(
        db=db,
        headers=headers,
        raw_event=raw_body,
    )

