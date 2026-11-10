"""Operational metrics and safe error classification for PAYFLOW AI (Prompt 40).

Collects operational counters in-memory without external infrastructure,
guaranteeing zero PII, zero secret logging, and safe categorized aggregation.
"""

from enum import Enum
import threading
from typing import Any, Dict, Optional


class ErrorCategory(str, Enum):
    """Standardized, safe error classifications without PII or internal secrets."""

    # API Categories
    API_VALIDATION_ERROR = "api_validation_error"
    API_AUTH_ERROR = "api_auth_error"
    API_RATE_LIMITED = "api_rate_limited"
    API_NOT_FOUND = "api_not_found"
    API_SERVER_ERROR = "api_server_error"

    # PayPal Failure Categories
    PAYPAL_AUTH_FAILURE = "paypal_auth_failure"
    PAYPAL_NETWORK_TIMEOUT = "paypal_network_timeout"
    PAYPAL_API_REJECTION = "paypal_api_rejection"
    PAYPAL_PAYLOAD_ERROR = "paypal_payload_error"

    # AI Provider Failure Categories
    AI_KEY_MISSING = "ai_key_missing"
    AI_RATE_LIMITED = "ai_rate_limited"
    AI_PROVIDER_UNAVAILABLE = "ai_provider_unavailable"
    AI_TOOL_EXECUTION_ERROR = "ai_tool_execution_error"

    # Webhook Verification Failure Categories
    WEBHOOK_SIGNATURE_INVALID = "webhook_signature_invalid"
    WEBHOOK_REPLAY_ATTACK = "webhook_replay_attack"
    WEBHOOK_FETCH_CERT_FAILED = "webhook_fetch_cert_failed"
    WEBHOOK_MALFORMED_HEADER = "webhook_malformed_header"

    # Scheduler Failure Categories
    SCHEDULER_JOB_ERROR = "scheduler_job_error"
    SCHEDULER_DB_UNAVAILABLE = "scheduler_db_unavailable"


class MetricsCollector:
    """Thread-safe in-memory operational metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        """Reset all metric counters to zero."""
        with self._lock:
            self.api_requests_total = 0
            self.api_errors_total: Dict[str, int] = {}
            self.paypal_requests_total = 0
            self.paypal_failures_total: Dict[str, int] = {}
            self.ai_requests_total = 0
            self.ai_failures_total: Dict[str, int] = {}
            self.webhook_events_total = 0
            self.webhook_failures_total: Dict[str, int] = {}
            self.scheduler_runs_total = 0
            self.scheduler_failures_total: Dict[str, int] = {}

    def record_request(self, method: str, path: str, status_code: int) -> None:
        """Record an incoming HTTP API request and categorize errors if >= 400."""
        with self._lock:
            self.api_requests_total += 1
            if status_code >= 400:
                cat = ErrorCategory.API_SERVER_ERROR.value
                if status_code in (400, 422):
                    cat = ErrorCategory.API_VALIDATION_ERROR.value
                elif status_code in (401, 403):
                    cat = ErrorCategory.API_AUTH_ERROR.value
                elif status_code == 404:
                    cat = ErrorCategory.API_NOT_FOUND.value
                elif status_code == 429:
                    cat = ErrorCategory.API_RATE_LIMITED.value
                self.api_errors_total[cat] = self.api_errors_total.get(cat, 0) + 1

    def record_paypal_call(self, success: bool, error_category: Optional[ErrorCategory] = None) -> None:
        """Record a PayPal REST API invocation outcome."""
        with self._lock:
            self.paypal_requests_total += 1
            if not success and error_category:
                cat_key = error_category.value if isinstance(error_category, ErrorCategory) else str(error_category)
                self.paypal_failures_total[cat_key] = self.paypal_failures_total.get(cat_key, 0) + 1

    def record_ai_call(self, success: bool, error_category: Optional[ErrorCategory] = None) -> None:
        """Record an AI provider generation or tool invocation outcome."""
        with self._lock:
            self.ai_requests_total += 1
            if not success and error_category:
                cat_key = error_category.value if isinstance(error_category, ErrorCategory) else str(error_category)
                self.ai_failures_total[cat_key] = self.ai_failures_total.get(cat_key, 0) + 1

    def record_webhook_event(self, success: bool, error_category: Optional[ErrorCategory] = None) -> None:
        """Record a PayPal webhook receipt and cryptographic verification outcome."""
        with self._lock:
            self.webhook_events_total += 1
            if not success and error_category:
                cat_key = error_category.value if isinstance(error_category, ErrorCategory) else str(error_category)
                self.webhook_failures_total[cat_key] = self.webhook_failures_total.get(cat_key, 0) + 1

    def record_scheduler_run(self, success: bool, error_category: Optional[ErrorCategory] = None) -> None:
        """Record a background reminder scheduler execution cycle."""
        with self._lock:
            self.scheduler_runs_total += 1
            if not success and error_category:
                cat_key = error_category.value if isinstance(error_category, ErrorCategory) else str(error_category)
                self.scheduler_failures_total[cat_key] = self.scheduler_failures_total.get(cat_key, 0) + 1

    def get_summary(self) -> Dict[str, Any]:
        """Produce an aggregated operational health summary without PII or secrets."""
        with self._lock:
            return {
                "api": {
                    "total_requests": self.api_requests_total,
                    "errors_by_category": dict(self.api_errors_total),
                    "error_rate_pct": (
                        round((sum(self.api_errors_total.values()) / max(self.api_requests_total, 1)) * 100, 2)
                    ),
                },
                "paypal": {
                    "total_calls": self.paypal_requests_total,
                    "failures_by_category": dict(self.paypal_failures_total),
                },
                "ai_provider": {
                    "total_calls": self.ai_requests_total,
                    "failures_by_category": dict(self.ai_failures_total),
                },
                "webhooks": {
                    "total_events": self.webhook_events_total,
                    "verification_failures": dict(self.webhook_failures_total),
                },
                "scheduler": {
                    "total_runs": self.scheduler_runs_total,
                    "failures_by_category": dict(self.scheduler_failures_total),
                },
            }


# Global metrics collector instance
metrics_collector = MetricsCollector()

