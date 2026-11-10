"""PAYFLOW AI FastAPI Application Entrypoint.

Handles lifespan events, database connection lifecycle, index verification,
CORS security, API routing, and safe health monitoring.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import logger
from app.db.mongodb import db_manager, get_db_status
from app.db.indexes import create_indexes

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management for startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' mode")

    # Validate production readiness or log actionable development notices
    if settings.is_production:
        missing = settings.validate_production_readiness()
        if missing:
            error_msg = "CRITICAL: Production startup failed due to missing required configurations:\n" + "\n".join(
                f"  - {item}" for item in missing
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    else:
        for msg in settings.get_actionable_startup_messages():
            logger.info(msg)

    # Initialize asynchronous MongoDB connection
    await db_manager.connect(
        uri=settings.MONGODB_URI,
        db_name=settings.MONGODB_DATABASE,
    )

    # Idempotently verify indexes if connected
    if db_manager.db is not None and db_manager.is_connected:
        await create_indexes(db_manager.db)

    try:
        yield
    finally:
        logger.info(f"Shutting down {settings.APP_NAME}")
        await db_manager.close()


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered Accounts Receivable Agent for Freelancers and Small Businesses",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
)

# Configure CORS strictly based on allowed origins from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

# Mount core API router
app.include_router(api_router)


@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, str]:
    """Public health status check.

    Returns operational service status and database state without exposing
    any secrets, connection URIs, or credential information.
    """
    db_status = await get_db_status()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "environment": settings.APP_ENV,
        "database": db_status,
    }


@app.get("/", tags=["Root"])
async def root() -> Dict[str, str]:
    """Root endpoint verifying API availability."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs": "/docs" if settings.APP_ENV != "production" else "disabled",
    }
