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

    If ``preimage_encryption_key`` is set it must be a valid 32-byte
    URL-safe base64 key (as produced by ``Fernet.generate_key()``).
    Otherwise a deterministic key is derived from ``jwt_secret_key`` so
    the application still starts in development without extra config —
    but production deployments **must** set PREIMAGE_ENCRYPTION_KEY.
    """
    key = settings.preimage_encryption_key
    if key:
        return Fernet(key.encode())
    # Derive a stable 32-byte key from the JWT secret (dev fallback only)
    derived = base64.urlsafe_b64encode(
        hashlib.sha256(settings.jwt_secret_key.encode()).digest()
    )
    return Fernet(derived)


def encrypt_preimage(preimage_hex: str) -> str:
    """
    Encrypt a hex-encoded LND preimage for storage.

    Returns a URL-safe base64 ciphertext string suitable for the
    ``InvoiceHold.preimage`` column.
    """
    fernet = _get_fernet()
    return fernet.encrypt(preimage_hex.encode()).decode()


def decrypt_preimage(ciphertext: str) -> str:
    """
    Decrypt a stored preimage ciphertext back to hex.

    Raises ``cryptography.fernet.InvalidToken`` if the ciphertext is
    tampered or the key is wrong.
    """
    fernet = _get_fernet()
    return fernet.decrypt(ciphertext.encode()).decode()


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
