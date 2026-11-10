"""Logging configuration for PAYFLOW AI with automatic secret scrubbing."""

import logging
import re
import sys

# Regular expressions detecting sensitive tokens, authorization credentials, and secrets
SECRET_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]+", re.IGNORECASE), "Bearer [MASKED]"),
    (
        re.compile(
            r"(password|client_secret|app_secret_key|secret|api_key|access_token|refresh_token)\s*[:=]\s*['\"]?[^\s,'\"]+['\"]?",
            re.IGNORECASE,
        ),
        r"\1=[MASKED]",
    ),
    (re.compile(r"access_token\$[A-Za-z0-9_\-]+", re.IGNORECASE), "access_token$[MASKED]"),
]


class SecretMaskingFilter(logging.Filter):
    """Filter that intercepts and masks tokens, passwords, and API secrets from log output."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern, repl in SECRET_PATTERNS:
                msg = pattern.sub(repl, msg)
            record.msg = msg
        return True


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure structured console logging without secret leakage."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(SecretMaskingFilter())

    root_logger = logging.getLogger("payflow")
    root_logger.setLevel(log_level)
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    else:
        for h in root_logger.handlers:
            h.addFilter(SecretMaskingFilter())

    return root_logger


def get_logger(name: str = "payflow") -> logging.Logger:
    """Retrieve logger instance for a given namespace."""
    return logging.getLogger(name)


logger = setup_logging()
