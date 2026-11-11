"""Asynchronous MongoDB connection management using motor.

Provides lifecycle management, connection ping verification, and clean
dependency injection for FastAPI routes.
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from bson import Decimal128
from bson.codec_options import CodecOptions, TypeCodec, TypeRegistry
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, PyMongoError
from app.core.logging import logger


class DecimalCodec(TypeCodec):
    """BSON codec converting Python Decimal to Decimal128 and back with full precision."""

    python_type = Decimal
    bson_type = Decimal128

    def transform_python(self, value: Decimal) -> Decimal128:
        return Decimal128(str(value))

    def transform_bson(self, value: Decimal128) -> Decimal:
        return value.to_decimal()


class DateCodec(TypeCodec):
    """BSON codec serializing pure datetime.date objects as ISO-8601 strings."""

    python_type = date
    bson_type = str

    def transform_python(self, value: date) -> str:
        return value.isoformat()

    def transform_bson(self, value: str) -> str:
        return value


def get_codec_options() -> CodecOptions:
    """Build standard BSON CodecOptions supporting Decimal, date, and UTC-aware datetimes."""
    type_registry = TypeRegistry([DecimalCodec(), DateCodec()])
    return CodecOptions(type_registry=type_registry, tz_aware=True)


class MongoDBManager:
    """Manages the AsyncIOMotorClient lifecycle and database access."""

    def __init__(self) -> None:
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self._connected: bool = False

    @property
    def is_connected(self) -> bool:
        """Return cached connectivity state."""
        return self._connected

    async def connect(self, uri: str, db_name: str, timeout_ms: int = 3000) -> None:
        """Initialize Motor client, configure timeouts, and verify connectivity."""
        try:
            logger.info("Initializing asynchronous MongoDB client...")
            self.client = AsyncIOMotorClient(
                uri,
                serverSelectionTimeoutMS=timeout_ms,
                connectTimeoutMS=timeout_ms,
            )
            self.db = self.client.get_database(db_name, codec_options=get_codec_options())

            # Verify connection with an explicit ping
            await self.ping()
            self._connected = True
            logger.info(f"MongoDB connected successfully to database: '{db_name}'")
        except (ConnectionFailure, PyMongoError) as err:
            self._connected = False
            logger.warning(
                f"MongoDB connection ping failed (host unreachable or timeout: {err}). "
                "Running in development mode with database disconnected."
            )

    async def ping(self) -> bool:
        """Send a lightweight ping command to verify database liveliness."""
        if self.client is None:
            self._connected = False
            return False
        try:
            await self.client.admin.command("ping")
            self._connected = True
            return True
        except Exception as err:
            self._connected = False
            logger.debug(f"MongoDB ping check failed: {err}")
            return False

    async def close(self) -> None:
        """Close Motor client connections cleanly."""
        if self.client is not None:
            logger.info("Closing MongoDB connection pool...")
            self.client.close()
            self.client = None
            self.db = None
            self._connected = False
            logger.info("MongoDB connection closed cleanly.")


# Singleton database manager instance
db_manager = MongoDBManager()


async def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency for accessing the database.

    Raises:
        RuntimeError: If database connection is not initialized.
    """
    if db_manager.db is None:
        raise RuntimeError("Database connection is not initialized. Check MongoDB status.")
    return db_manager.db


async def get_db_status() -> str:
    """Check and return database operational status without leaking credentials."""
    if db_manager.client is None:
        return "disconnected"
    is_alive = await db_manager.ping()
    return "connected" if is_alive else "disconnected"
