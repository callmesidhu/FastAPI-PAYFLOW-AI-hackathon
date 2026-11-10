"""AI Assistant & Natural Language Invoice Extraction Endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.core.rate_limit import rate_limit_ai_dependency
from app.db.mongodb import get_db
from app.models.user import User
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    ConfirmExtractedInvoiceRequest,
    InvoiceExtractionRequest,
    InvoiceExtractionResponse,
)
from app.schemas.invoice import InvoiceResponse
from app.agents.orchestrator import AIAssistantOrchestrator
from app.services.invoice_extractor import InvoiceExtractor

router = APIRouter(prefix="/ai", tags=["AI Assistant"])
orchestrator = AIAssistantOrchestrator()


@router.post(
    "/chat",
    response_model=AIChatResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_ai_dependency)],
    summary="Chat with PAYFLOW AI Assistant",
    description=(
        "Conversational AI assistant for accounts receivable. Supports natural language queries, "
        "invoice draft creation, overdue analysis, and reminder drafting with strict human-in-the-loop "
        "authorization for sensitive actions."
    ),
)
async def chat_with_assistant(
    payload: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AIChatResponse:
    return await orchestrator.run_turn(
        db=db,
        user=current_user,
        user_message=payload.message,
        conversation_id=payload.conversation_id,
    )


@router.post(
    "/extract-invoice",
    response_model=InvoiceExtractionResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_ai_dependency)],
    summary="Extract structured invoice draft from natural language",
    description=(
        "Parses unstructured natural language instructions into an editable invoice draft preview. "
        "Resolves customer identity against the authenticated user's records, handles relative dates "
        "with timezone disclosure, and produces an unconfirmed suggestion without writing to the database."
    ),
)
async def extract_invoice_from_text(
    payload: InvoiceExtractionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> InvoiceExtractionResponse:
    return await InvoiceExtractor.extract_invoice(
        db=db,
        user_id=current_user.id,
        text=payload.text,
        user_timezone=payload.timezone or "UTC",
    )


@router.post(
    "/confirm-extracted-invoice",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_ai_dependency)],
    summary="Confirm and save extracted invoice as draft",
    description=(
        "Takes the user-confirmed and edited invoice fields, performs authoritative server-side "
        "revalidation (customer ownership, positive prices, valid dates, Decimal precision), "
        "and saves the invoice with status='draft'. Does not send to PayPal."
    ),
)
async def confirm_extracted_invoice(
    payload: ConfirmExtractedInvoiceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> InvoiceResponse:
    try:
        return await InvoiceExtractor.confirm_extracted_draft(
            db=db,
            user_id=current_user.id,
            payload=payload,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
