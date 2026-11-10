"""API router aggregator."""

from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.customers import router as customers_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.invoices import router as invoices_router

api_router = APIRouter(prefix="/api")

# Mount route modules
api_router.include_router(auth_router)
api_router.include_router(approvals_router)
api_router.include_router(customers_router)
api_router.include_router(invoices_router)
api_router.include_router(dashboard_router)
