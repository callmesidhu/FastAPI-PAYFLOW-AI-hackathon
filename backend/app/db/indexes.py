"""MongoDB Index definitions and idempotent initialization for PAYFLOW AI.

Defines required indexes across MVP collections:
- users
- customers
- invoices
- approvals
- reminders
- transactions
- audit_logs
- webhook_events
"""

from typing import Any, Dict, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import PyMongoError
from app.core.logging import logger

COLLECTIONS_MVP = [
    "users",
    "customers",
    "invoices",
    "approvals",
    "reminders",
    "transactions",
    "audit_logs",
    "webhook_events",
]

INDEX_DEFINITIONS: Dict[str, List[IndexModel]] = {
    "users": [
        IndexModel([("email", ASCENDING)], unique=True, name="idx_users_email_unique"),
        IndexModel([("created_at", DESCENDING)], name="idx_users_created_at"),
    ],
    "customers": [
        IndexModel([("user_id", ASCENDING)], name="idx_customers_user_id"),
        IndexModel(
            [("user_id", ASCENDING), ("email", ASCENDING)],
            unique=True,
            sparse=True,
            name="idx_customers_user_email_unique",
        ),
        IndexModel([("user_id", ASCENDING), ("name", ASCENDING)], name="idx_customers_user_name"),
        IndexModel([("created_at", DESCENDING)], name="idx_customers_created_at"),
    ],
    "invoices": [
        IndexModel([("internal_id", ASCENDING)], unique=True, name="idx_invoices_internal_id_unique"),
        IndexModel([("user_id", ASCENDING)], name="idx_invoices_user_id"),
        IndexModel(
            [("user_id", ASCENDING), ("invoice_number", ASCENDING)],
            unique=True,
            name="idx_invoices_user_number_unique",
        ),
        IndexModel([("paypal_invoice_id", ASCENDING)], sparse=True, name="idx_invoices_paypal_id"),
        IndexModel([("user_id", ASCENDING), ("status", ASCENDING)], name="idx_invoices_user_status"),
        IndexModel([("status", ASCENDING)], name="idx_invoices_status"),
        IndexModel([("due_date", ASCENDING)], name="idx_invoices_due_date"),
        IndexModel([("customer_id", ASCENDING)], name="idx_invoices_customer_id"),
        IndexModel([("created_at", DESCENDING)], name="idx_invoices_created_at"),
    ],
    "approvals": [
        IndexModel([("user_id", ASCENDING)], name="idx_approvals_user_id"),
        IndexModel([("resource_id", ASCENDING)], name="idx_approvals_resource_id"),
        IndexModel([("payload_hash", ASCENDING)], name="idx_approvals_payload_hash"),
        IndexModel([("user_id", ASCENDING), ("status", ASCENDING)], name="idx_approvals_user_status"),
        IndexModel([("created_at", DESCENDING)], name="idx_approvals_created_at"),
    ],
    "reminders": [
        IndexModel([("user_id", ASCENDING)], name="idx_reminders_user_id"),
        IndexModel([("invoice_id", ASCENDING)], name="idx_reminders_invoice_id"),
        IndexModel(
            [("invoice_id", ASCENDING), ("stage", ASCENDING)],
            unique=True,
            name="idx_reminders_invoice_stage_unique",
        ),
        IndexModel([("status", ASCENDING)], name="idx_reminders_status"),
        IndexModel([("created_at", DESCENDING)], name="idx_reminders_created_at"),
    ],
    "transactions": [
        IndexModel([("user_id", ASCENDING)], name="idx_transactions_user_id"),
        IndexModel([("invoice_id", ASCENDING)], name="idx_transactions_invoice_id"),
        IndexModel([("paypal_capture_id", ASCENDING)], sparse=True, name="idx_transactions_paypal_capture_id"),
        IndexModel([("created_at", DESCENDING)], name="idx_transactions_created_at"),
    ],
    "audit_logs": [
        IndexModel([("user_id", ASCENDING)], name="idx_audit_logs_user_id"),
        IndexModel([("resource_id", ASCENDING)], name="idx_audit_logs_resource_id"),
        IndexModel([("action", ASCENDING)], name="idx_audit_logs_action"),
        IndexModel([("created_at", DESCENDING)], name="idx_audit_logs_created_at"),
    ],
    "webhook_events": [
        IndexModel([("event_id", ASCENDING)], unique=True, name="idx_webhook_events_id_unique"),
        IndexModel([("created_at", DESCENDING)], name="idx_webhook_events_created_at"),
    ],
}


async def create_indexes(db: AsyncIOMotorDatabase) -> Dict[str, List[str]]:
    """Idempotently create indexes across all core collections.

    Returns:
        Dict mapping collection name to list of created index names.
    """
    results: Dict[str, List[str]] = {}
    for collection_name, indexes in INDEX_DEFINITIONS.items():
        try:
            collection = db[collection_name]
            created = await collection.create_indexes(indexes)
            results[collection_name] = created
            logger.debug(f"Idempotent indexes verified for '{collection_name}': {len(created)} index(es)")
        except PyMongoError as err:
            logger.warning(f"Notice during index creation on '{collection_name}': {err}")
            results[collection_name] = []
    logger.info("MongoDB idempotent index verification completed.")
    return results
