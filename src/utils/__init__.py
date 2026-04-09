"""
Shared utility helpers for SatsRemit.

Centralises small functions that were previously scattered across service
and route modules so they can be reused and tested independently.
"""

import hashlib
import secrets
from datetime import datetime


def generate_reference() -> str:
    """
    Generate a unique 20-character transfer reference.

    Format: ``YYMMDDHHMMSS`` (12 chars) + 8 random hex chars = 20 chars total.
    The timestamp prefix makes references roughly time-sortable while the
    random suffix prevents collisions within the same second.
    """
    timestamp = datetime.utcnow().strftime("%y%m%d%H%M%S")  # 12 chars
    random_suffix = secrets.token_hex(4)                    # 8 chars
    return f"{timestamp}{random_suffix}"


def normalise_phone(phone: str) -> str:
    """
    Normalise a phone number to a digits-only string without leading ``+``.

    Strips spaces, dashes, and the leading ``+`` so the result is safe to
    pass to the WhatsApp Business API (which expects no ``+``).

    Examples::

        normalise_phone("+27821234567") -> "27821234567"
        normalise_phone("27-82 123 4567") -> "27821234567"
    """
    return phone.replace("+", "").replace("-", "").replace(" ", "")


def hash_phone(phone: str) -> str:
    """
    Return a short SHA-256-derived fingerprint of a phone number.

    Used for privacy-preserving deduplication checks without storing the
    raw phone number in analytics tables.  The result is the first 16 hex
    characters of the SHA-256 digest (64-bit prefix — suitable for
    approximate matching, not cryptographic identity).
    """
    return hashlib.sha256(normalise_phone(phone).encode()).hexdigest()[:16]


__all__ = [
    "generate_reference",
    "normalise_phone",
    "hash_phone",
]
