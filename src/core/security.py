"""
Security utilities - JWT, password hashing, auth
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials

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
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create JWT token

    Args:
        subject: Token subject (e.g., "agent:{agent_id}")
        agent_id: Optional agent ID for agent tokens
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


def verify_pin(hashed_pin: str, provided_pin: str) -> bool:
    """Verify PIN against hash"""
    # Simple comparison for now - in production use proper hashing
    return hashed_pin == hash_password(provided_pin)
