"""API router aggregator."""

from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.customers import router as customers_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.invoices import router as invoices_router
from app.api.v1.paypal import router as paypal_router
from app.api.v1.ai import router as ai_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.reminders import router as reminders_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.audit import router as audit_router
from app.api.v1.diagnostics import router as diagnostics_router

api_router = APIRouter(prefix="/api")

# Mount route modules
api_router.include_router(auth_router)
api_router.include_router(approvals_router)
api_router.include_router(customers_router)
api_router.include_router(invoices_router)
api_router.include_router(dashboard_router)
api_router.include_router(paypal_router)
api_router.include_router(ai_router)
api_router.include_router(analytics_router)
api_router.include_router(reminders_router)
api_router.include_router(webhooks_router)
api_router.include_router(audit_router)
api_router.include_router(diagnostics_router)


