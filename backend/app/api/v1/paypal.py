"""PayPal Sandbox integration and diagnostic API endpoints."""

from fastapi import APIRouter, Depends, Path, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.db.mongodb import get_db
from app.models.enums import ActionType, ApprovalStatus
from app.models.user import User
from app.schemas.paypal import (
    PayPalInvoiceCreateRequest,
    PayPalInvoiceCreateResponse,
    PayPalInvoiceSendRequest,
    PayPalInvoiceSendResponse,
    PayPalStatusResponse,
)
from app.services.approval_service import approve_action
from app.services.invoice_service import (
    create_approved_paypal_invoice,
    send_approved_paypal_invoice,
)
from app.services.paypal_service import paypal_service

router = APIRouter(prefix="/paypal", tags=["PayPal"])


@router.get(
    "/status",
    response_model=PayPalStatusResponse,
    summary="PayPal Sandbox Diagnostic Status",
    description=(
        "Check PayPal Developer Sandbox connectivity, OAuth token validity, and webhook configuration. "
        "Credentials remain server-side; secrets and raw access tokens are never exposed."
    ),
)
async def get_paypal_status(
    current_user: User = Depends(get_current_user),
) -> PayPalStatusResponse:
    info = await paypal_service.check_connection()
    return PayPalStatusResponse.model_validate(info)


@router.post(
    "/invoices",
    response_model=PayPalInvoiceCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create PayPal Sandbox Invoice",
    description=(
        "Dispatches an approved invoice to PayPal Sandbox via Invoicing API v2. "
        "Strictly verifies human authorization, payload hash integrity, and prevents duplicate executions."
    ),
)
async def create_paypal_invoice_endpoint(
    payload: PayPalInvoiceCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PayPalInvoiceCreateResponse:
    return await create_approved_paypal_invoice(
        db=db,
        user=current_user,
        invoice_id=payload.invoice_id,
        approval_id=payload.approval_id,
        idempotency_key=payload.idempotency_key,
    )


@router.post(
    "/invoices/{invoice_id}/send",
    response_model=PayPalInvoiceSendResponse,
    status_code=status.HTTP_200_OK,
    summary="Send Invoice via PayPal Sandbox",
    description=(
        "Dispatches an existing approved invoice to the customer via PayPal Invoicing API v2. "
        "Strictly verifies human approval, prevents duplicate sends, and reconciles network timeouts."
    ),
)
async def send_paypal_invoice_endpoint(
    invoice_id: str = Path(..., description="Internal invoice UUID"),
    payload: PayPalInvoiceSendRequest = PayPalInvoiceSendRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PayPalInvoiceSendResponse:
    return await send_approved_paypal_invoice(
        db=db,
        user=current_user,
        invoice_id=invoice_id,
        approval_id=payload.approval_id,
        idempotency_key=payload.idempotency_key,
        note=payload.note,
        send_to_recipient=payload.send_to_recipient,
        send_to_invoicer=payload.send_to_invoicer,
    )


@router.post(
    "/invoices/{invoice_id}/approve-and-send",
    response_model=PayPalInvoiceSendResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve and Send via PayPal Sandbox",
    description=(
        "Atomic operation: Authorizes pending invoice action and executes dispatch to customer via PayPal Sandbox. "
        "Intended for one-click human authorization in the UI."
    ),
)
async def approve_and_send_endpoint(
    invoice_id: str = Path(..., description="Internal invoice UUID"),
    payload: PayPalInvoiceSendRequest = PayPalInvoiceSendRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PayPalInvoiceSendResponse:
    # 1. Check if there is a pending approval that can be authorized
    appr_doc = await db.approvals.find_one({
        "user_id": current_user.id,
        "resource_type": "invoice",
        "resource_id": invoice_id,
        "status": ApprovalStatus.PENDING.value,
    })
    if appr_doc:
        await approve_action(db, current_user.id, appr_doc["id"])

    # 2. Execute send
    return await send_approved_paypal_invoice(
        db=db,
        user=current_user,
        invoice_id=invoice_id,
        approval_id=payload.approval_id,
        idempotency_key=payload.idempotency_key,
        note=payload.note,
        send_to_recipient=payload.send_to_recipient,
        send_to_invoicer=payload.send_to_invoicer,
    )


