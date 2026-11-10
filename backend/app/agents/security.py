"""Security filters, secret scrubbing, and prompt injection defense.

Guarantees:
1. PayPal client secrets, access tokens, passwords, and connection strings
   are strictly scrubbed before any data is sent to an external LLM.
2. External text (customer notes, invoice descriptions) is treated as
   untrusted and isolated to prevent prompt injection.
"""

import re
from typing import Any, Dict

# Known sensitive patterns
SECRET_PATTERNS = [
    # Bearer tokens and JWTs
    re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]+", re.IGNORECASE),
    re.compile(r"eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+"),
    # PayPal tokens and secret prefixes
    re.compile(r"A21AA[A-Za-z0-9\-_]+"),
    re.compile(r"(?:client_secret|client_id|secret_key|api_key|password)\s*[:=]\s*['\"]?([A-Za-z0-9\-_\.]{8,})['\"]?", re.IGNORECASE),
    # MongoDB connection URIs
    re.compile(r"mongodb(?:\+srv)?://[^\s'\"<>]+", re.IGNORECASE),
    # Argon2 password hashes
    re.compile(r"\$argon2id\$[^\s]+"),
]

# Injection phrases to neutralize
INJECTION_SIGNATURES = [
    re.compile(r"(?:ignore\s+all\s+(?:previous|prior)\s+instructions)", re.IGNORECASE),
    re.compile(r"(?:disregard\s+system\s+(?:prompt|instructions))", re.IGNORECASE),
    re.compile(r"(?:you\s+are\s+now\s+in\s+developer\s+mode)", re.IGNORECASE),
    re.compile(r"(?:system\s+override\s*:\s*)", re.IGNORECASE),
    re.compile(r"(?:bypass\s+(?:approval|human|policy)\s+(?:check|engine|step))", re.IGNORECASE),
    re.compile(r"(?:approve\s+and\s+send\s+automatically\s+without\s+asking)", re.IGNORECASE),
]


def scrub_secrets(text: str) -> str:
    """Scrub sensitive credentials, secrets, and auth tokens from text.

    Replaces any matched credentials with '[REDACTED_SECRET]'.
    """
    if not text:
        return text

    scrubbed = text
    for pattern in SECRET_PATTERNS:
        scrubbed = pattern.sub("[REDACTED_SECRET]", scrubbed)

    return scrubbed


def sanitize_untrusted_input(text: str) -> str:
    """Neutralize potential prompt injection attempts from customer notes or external inputs."""
    if not text:
        return ""

    sanitized = text
    for pattern in INJECTION_SIGNATURES:
        sanitized = pattern.sub("[UNTRUSTED_INSTRUCTION_REMOVED]", sanitized)

    return sanitized.strip()


def wrap_untrusted_content(label: str, content: str) -> str:
    """Wrap untrusted user/external content in clear structural boundary tags.

    Ensures the LLM understands this content is data, NOT instructions.
    """
    clean = sanitize_untrusted_input(content)
    scrubbed = scrub_secrets(clean)
    return f"<{label}_data_boundary is_untrusted='true'>\n{scrubbed}\n</{label}_data_boundary>"

