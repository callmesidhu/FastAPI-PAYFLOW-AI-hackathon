"""Pydantic request and response schemas."""

from app.schemas.auth import AuthTokenResponse, UserLogin, UserRegister, UserResponse
from app.schemas.dashboard import CurrencySummary, DashboardSummaryResponse, TrendItem
from app.schemas.customer import CustomerCreate, CustomerListResponse, CustomerResponse, CustomerUpdate
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceItemCreate,
    InvoiceItemResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceUpdate,
    SubmitForApprovalResponse,
)

__all__ = [
    "AuthTokenResponse",
    "CurrencySummary",
    "CustomerCreate",
    "CustomerListResponse",
    "CustomerResponse",
    "CustomerUpdate",
    "DashboardSummaryResponse",
    "InvoiceCreate",
    "InvoiceItemCreate",
    "InvoiceItemResponse",
    "InvoiceListResponse",
    "InvoiceResponse",
    "InvoiceUpdate",
    "SubmitForApprovalResponse",
    "UserLogin",
    "UserRegister",
    "UserResponse",
]
