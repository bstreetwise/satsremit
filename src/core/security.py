"""
Security utilities - JWT, password hashing, auth, encryption
"""

import base64
import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Optional

import jwt
from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials as HTTPAuthCredentials

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer scheme
security = HTTPBearer()

settings = get_settings()


class TokenPayload:
    """JWT token payload"""
    def __init__(self, subject: str, agent_id: Optional[str] = None, exp: Optional[datetime] = None):
        self.subject = subject  # Can be "sender", "agent", "admin"
        self.agent_id = agent_id  # For agent tokens
        self.exp = exp or datetime.utcnow() + timedelta(hours=settings.jwt_expiry_hours)
        self.iat = datetime.utcnow()


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_token(
    subject: str,
    agent_id: Optional[str] = None,
    is_admin: bool = False,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create JWT token

    Args:
        subject: Token subject (e.g., "agent:{agent_id}")
        agent_id: Optional agent ID for agent tokens
        is_admin: Whether this token grants admin privileges
        expires_delta: Optional custom expiry

    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiry_hours)

    to_encode = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.utcnow(),
        "agent_id": agent_id,
        "is_admin": is_admin,
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and verify JWT token

    Args:
        token: JWT token string

    Returns:
        Token payload dict or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        logger.warning("Invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_token_from_header(credentials: HTTPAuthCredentials = Depends(security)) -> str:
    """Extract token from Authorization header"""
    return credentials.credentials


async def get_current_agent(token: str = Depends(get_token_from_header)) -> dict:
    """
    Get current authenticated agent from token

    Returns:
        Token payload with agent info
    """
    payload = decode_token(token)

    if not payload.get("agent_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not an agent token",
        )

    return payload


async def get_current_admin(token: str = Depends(get_token_from_header)) -> dict:
    """
    Get current authenticated admin from token.

    Agents with ``is_admin=True`` are issued tokens that include
    ``"is_admin": True`` in the payload.  This dependency rejects any
    token that lacks that claim, so ordinary agent tokens cannot reach
    admin endpoints.

    Returns:
        Token payload with agent + admin info
    """
    payload = decode_token(token)

    if not payload.get("agent_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not an agent token",
        )

    if not payload.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return payload


async def verify_webhook_signature(
    token: str = Depends(get_token_from_header),
) -> str:
    """
    Verify webhook request signature (LND webhooks)

    For production, implement HMAC-SHA256 verification
    """
    payload = decode_token(token)
    return payload.get("sub")


def generate_pin() -> str:
    """Generate 4-digit PIN"""
    import secrets
    return f"{secrets.randbelow(10000):04d}"


def hash_pin(pin: str) -> str:
    """Hash a 4-digit PIN using bcrypt"""
    return pwd_context.hash(pin)


def verify_pin(hashed_pin: str, provided_pin: str) -> bool:
    """Verify a plain PIN against its bcrypt hash"""
    return pwd_context.verify(provided_pin, hashed_pin)


def _get_fernet() -> Fernet:
    """
    Return a Fernet instance keyed from settings.

    Key priority:
    1. ``settings.preimage_encryption_key`` — must be a URL-safe base64 key
       produced by ``Fernet.generate_key()``.  Required in production.
    2. Dev fallback — a key derived from ``jwt_secret_key`` via SHA-256.
       Acceptable in development/test so the app boots without extra config,
       but **raises** ``RuntimeError`` if the environment is "production"
       to ensure the fallback can never silently reach live deployments.

    Raises:
        RuntimeError: If called in production without a dedicated
            ``PREIMAGE_ENCRYPTION_KEY``.
        ValueError: If ``preimage_encryption_key`` is set but malformed.
    """
    key = settings.preimage_encryption_key
    if key:
        try:
            return Fernet(key.encode())
        except Exception as exc:
            raise ValueError(
                "PREIMAGE_ENCRYPTION_KEY is set but is not a valid Fernet key. "
                "Generate one with: python -c \"from cryptography.fernet import "
                "Fernet; print(Fernet.generate_key().decode())\""
            ) from exc

    # No dedicated key — use the dev fallback.
    if settings.environment == "production":
        raise RuntimeError(
            "PREIMAGE_ENCRYPTION_KEY must be set in production. "
            "The JWT-secret-derived fallback key is not safe for live deployments "
            "because rotating the JWT secret would invalidate all stored preimage "
            "ciphertexts.  Generate a dedicated key with: "
            "python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )

    # Derive a stable 32-byte key from the JWT secret (dev / test only).
    derived = base64.urlsafe_b64encode(
        hashlib.sha256(settings.jwt_secret_key.encode()).digest()
    )
    return Fernet(derived)


def encrypt_preimage(preimage_hex: str) -> str:
    """
    Encrypt a hex-encoded LND preimage for secure storage.

    The plaintext **must** be a 64-character lowercase hex string
    (the output of ``secrets.token_hex(32)``).  Passing any other value
    will encrypt successfully but ``decrypt_preimage`` will return the
    same non-hex string — callers are responsible for validating the
    plaintext before calling LND's settle endpoint.

    Returns:
        A URL-safe Fernet ciphertext string.  Length is approximately
        180–220 characters for a 64-char plaintext — ensure the target
        column is at least ``String(512)``.
    """
    if not isinstance(preimage_hex, str) or len(preimage_hex) != 64:
        raise ValueError(
            f"preimage_hex must be a 64-character hex string, got {len(preimage_hex)!r} chars"
        )
    fernet = _get_fernet()
    return fernet.encrypt(preimage_hex.encode()).decode()


def decrypt_preimage(ciphertext: str) -> str:
    """
    Decrypt a stored Fernet ciphertext back to the original hex preimage.

    Args:
        ciphertext: The value stored in ``InvoiceHold.preimage``.

    Returns:
        64-character hex string suitable for LND's ``settle_invoice`` call.

    Raises:
        ``cryptography.fernet.InvalidToken``: If the ciphertext is
            corrupted, truncated, or was encrypted with a different key.
    """
    fernet = _get_fernet()
    return fernet.decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# SQLAlchemy TypeDecorator — transparent encryption at the persistence layer
# ---------------------------------------------------------------------------

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


class EncryptedPreimage(TypeDecorator):
    """
    SQLAlchemy column type that transparently encrypts preimage values on
    write and decrypts them on read.

    Usage in a model::

        class InvoiceHold(Base):
            preimage = Column(EncryptedPreimage(512), nullable=False)

    **Why a TypeDecorator instead of application-layer calls?**

    Placing the encrypt/decrypt logic here means:

    - Every ORM write path (``session.add``, ``session.merge``,
      ``session.execute`` with an ORM-mapped insert) automatically
      encrypts.  A developer cannot accidentally bypass it by forgetting
      to call ``encrypt_preimage()`` manually.
    - Any direct DB read through the ORM (``session.query``,
      ``session.get``) automatically decrypts — the caller never handles
      raw ciphertext.
    - Bulk inserts that bypass the ORM (e.g. ``session.execute(insert(...))``
      with raw values) are the only exception; those paths must call
      ``encrypt_preimage`` explicitly, which is the expected behaviour for
      low-level operations.

    The column is stored as ``VARCHAR(512)`` in the database.  Fernet
    output for a 64-char plaintext is ~180 characters; 512 gives safe
    headroom for longer inputs and future algorithm changes.
    """

    impl = String
    cache_ok = True   # Fernet key comes from settings, not the type itself

    def __init__(self, length: int = 512, **kwargs):
        super().__init__(length, **kwargs)

    def process_bind_param(self, value, dialect):
        """Encrypt on write (Python → DB)."""
        if value is None:
            return None
        # If it's already a ciphertext (starts with the Fernet header byte
        # gAAAAA…) don't double-encrypt.  This guards against accidental
        # double-wrapping if the caller passes an already-encrypted value.
        if isinstance(value, str) and value.startswith("gAAAAA"):
            logger.warning(
                "EncryptedPreimage.process_bind_param received what looks like "
                "an already-encrypted value — storing as-is to avoid double encryption. "
                "Pass the plaintext hex preimage, not the ciphertext."
            )
            return value
        return encrypt_preimage(value)

    def process_result_value(self, value, dialect):
        """Decrypt on read (DB → Python)."""
        if value is None:
            return None
        return decrypt_preimage(value)


def verify_webhook_hmac(body: bytes, signature_header: str) -> bool:
    """
    Verify an HMAC-SHA256 webhook signature.

    LND (or any caller) should include the header::

        X-Webhook-Signature: sha256=<hex_digest>

    Args:
        body: Raw request body bytes.
        signature_header: Value of the ``X-Webhook-Signature`` header.

    Returns:
        True if the signature is valid.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    provided_digest = signature_header[len("sha256="):]
    expected_digest = hmac.new(
        settings.webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_digest, provided_digest)
