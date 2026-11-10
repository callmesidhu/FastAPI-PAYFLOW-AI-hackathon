"""Unit and contract tests for MongoDB connection lifecycle, indexes, and health checks.

Runs completely isolated with mocks; never requires production credentials.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import ASGITransport, AsyncClient
from app.db.mongodb import MongoDBManager, get_db, get_db_status
from app.db.indexes import COLLECTIONS_MVP, INDEX_DEFINITIONS, create_indexes
from app.main import app


@pytest.mark.asyncio
async def test_db_manager_connect_and_clean_shutdown():
    """Verify clean connect and shutdown lifecycle."""
    manager = MongoDBManager()
    mock_client = MagicMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1.0})
    mock_client.close = MagicMock()

    with patch("app.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        await manager.connect("mongodb://localhost:27017", "test_db")
        assert manager.is_connected is True
        assert manager.db is not None
        mock_client.admin.command.assert_awaited_once_with("ping")

        # Test clean close
        await manager.close()
        assert manager.is_connected is False
        assert manager.client is None
        assert manager.db is None
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_idempotent_index_creation():
    """Verify indexes are created across all collections idempotently."""
    mock_db = MagicMock()
    collections_dict = {}

    for col_name in COLLECTIONS_MVP:
        mock_col = MagicMock()
        mock_col.create_indexes = AsyncMock(return_value=[f"{col_name}_idx_1", f"{col_name}_idx_2"])
        collections_dict[col_name] = mock_col

    mock_db.__getitem__.side_effect = lambda name: collections_dict.get(name, MagicMock())

    # First call
    results_run1 = await create_indexes(mock_db)
    assert set(results_run1.keys()) == set(INDEX_DEFINITIONS.keys())

    # Second call (verifying idempotency)
    results_run2 = await create_indexes(mock_db)
    assert set(results_run2.keys()) == set(INDEX_DEFINITIONS.keys())

    # Verify all MVP collections are accounted for
    for col_name in COLLECTIONS_MVP:
        assert col_name in results_run1


@pytest.mark.asyncio
async def test_health_reports_database_status_without_leaking_credentials():
    """Verify /health reflects DB status without leaking connection strings or credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test default/disconnected state
        with patch("app.main.get_db_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = "connected"
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data.get("database") == "connected"

            text_payload = response.text
            assert "mongodb" not in text_payload.lower()
            assert "27017" not in text_payload
            assert "password" not in text_payload.lower()
            assert "uri" not in text_payload.lower()

        # Test disconnected state
        with patch("app.main.get_db_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = "disconnected"
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data.get("database") == "disconnected"


@pytest.mark.asyncio
async def test_get_db_dependency_raises_when_uninitialized():
    """Ensure get_db dependency raises descriptive error if DB is accessed before initialization."""
    with patch("app.db.mongodb.db_manager.db", None):
        with pytest.raises(RuntimeError) as exc_info:
            await get_db()
        assert "Database connection is not initialized" in str(exc_info.value)
