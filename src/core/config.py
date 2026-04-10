"""
Application configuration and settings
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from functools import lru_cache
from typing import Self
import logging

# ---------------------------------------------------------------------------
# Known placeholder values that must never reach a running server.
# Any value in this set causes Settings() to raise immediately at parse time.
# ---------------------------------------------------------------------------
_PLACEHOLDER_SECRETS: frozenset[str] = frozenset({
    "your-secret-key-change-in-production",
    "your-webhook-secret",
    "change-me",
    "changeme",
    "secret",
    "password",
    "example",
    "placeholder",
    "replace-me",
    "todo",
})

# Minimum acceptable byte-length for secrets (after hex/base64 decoding is
# irrelevant — we just measure the raw string length as a proxy for entropy).
_MIN_JWT_SECRET_LEN: int = 32
_MIN_WEBHOOK_SECRET_LEN: int = 16


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # Core
    debug: bool = False
    environment: str = "development"  # development, staging, production

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Database
    database_url: str
    database_echo: bool = False

    # Redis
    redis_url: str

    # LND Configuration
    lnd_rest_url: str
    lnd_macaroon_path: str
    lnd_cert_path: str
    lnd_hold_invoice_expiry_minutes: int = 5760  # 96 hours
    lnd_invoice_timeout_hours: float = 6.5

    # Bitcoin
    bitcoin_network: str = "testnet"  # testnet or mainnet
    bitcoin_rpc_url: str = "http://localhost:18332"
    bitcoin_rpc_user: str = "bitcoin"
    bitcoin_rpc_password: str = "password"

    # WhatsApp Business API
    whatsapp_business_account_id: str
    whatsapp_business_phone_number_id: str
    whatsapp_business_access_token: str

    # Rate feeds
    rate_source: str = "coingecko"
    rate_cache_minutes: int = 5

    # Platform Settings
    platform_fee_percent: float = 0.5
    agent_commission_percent: float = 0.5
    min_transfer_zar: float = 100.0
    max_transfer_zar: float = 500.0
    pin_expiry_minutes: int = 5

    # Security
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    rate_limit_requests: int = 5
    rate_limit_window_minutes: int = 60
    webhook_secret: str
    # 32-byte URL-safe base64-encoded key for Fernet preimage encryption.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    preimage_encryption_key: str = ""

    # Payment Methods
    allowed_withdrawal_methods: str = "bank_transfer,physical_cash,mobile_money"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text

    # Agent Settings
    agent_location_code: str = "ZWE_HRR"
    verification_timeout_minutes: int = 60
    auto_refund_after_hours: int = 1

    # ------------------------------------------------------------------
    # Secret validators — run at parse time, before any app code starts.
    # Pydantic raises ValueError immediately if any check fails; the
    # process exits with a clear message rather than starting with a
    # compromised security configuration.
    # ------------------------------------------------------------------

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        """
        Reject placeholder values and enforce a minimum length.

        A short or well-known secret makes HMAC-SHA256 JWT signatures
        trivially brute-forceable offline.  32 characters is the absolute
        minimum; 64+ (e.g. ``secrets.token_hex(32)``) is recommended.
        """
        if v.lower() in _PLACEHOLDER_SECRETS:
            raise ValueError(
                "\n\nJWT_SECRET_KEY is still set to the example placeholder value.\n"
                "Generate a strong secret with:\n\n"
                "    python -c \"import secrets; print(secrets.token_hex(32))\"\n\n"
                "and set it in your .env file before starting the server."
            )
        if len(v) < _MIN_JWT_SECRET_LEN:
            raise ValueError(
                f"\n\nJWT_SECRET_KEY is too short ({len(v)} chars). "
                f"Minimum is {_MIN_JWT_SECRET_LEN} characters.\n"
                "Generate a strong secret with:\n\n"
                "    python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            )
        return v

    @field_validator("webhook_secret")
    @classmethod
    def validate_webhook_secret(cls, v: str) -> str:
        """
        Reject placeholder webhook secrets.

        A guessable webhook secret allows an attacker to forge LND
        invoice-settled callbacks and fraudulently trigger payouts.
        """
        if v.lower() in _PLACEHOLDER_SECRETS:
            raise ValueError(
                "\n\nWEBHOOK_SECRET is still set to the example placeholder value.\n"
                "Generate a strong secret with:\n\n"
                "    python -c \"import secrets; print(secrets.token_hex(32))\"\n\n"
                "and set it in your .env file before starting the server."
            )
        if len(v) < _MIN_WEBHOOK_SECRET_LEN:
            raise ValueError(
                f"\n\nWEBHOOK_SECRET is too short ({len(v)} chars). "
                f"Minimum is {_MIN_WEBHOOK_SECRET_LEN} characters.\n"
            )
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Self:
        """
        Additional checks that only apply in production.

        In development/test it is acceptable to run without a
        ``PREIMAGE_ENCRYPTION_KEY`` (the code falls back to deriving
        one from the JWT secret).  In production this fallback is
        unsafe because JWT secret rotation would invalidate all stored
        preimage ciphertexts.
        """
        if self.environment == "production":
            if not self.preimage_encryption_key:
                raise ValueError(
                    "\n\nPREIMAGE_ENCRYPTION_KEY must be set in production.\n"
                    "Generate one with:\n\n"
                    "    python -c \"from cryptography.fernet import Fernet; "
                    "print(Fernet.generate_key().decode())\"\n"
                )
            if self.debug:
                raise ValueError(
                    "\n\nDEBUG=true must not be set in production. "
                    "Set DEBUG=false in your .env file.\n"
                )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = False
        # Allow extra env vars in .env that aren't defined in Settings
        # (e.g. API_TITLE, API_VERSION set by Docker Compose, etc.)
        extra = "ignore"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def withdrawal_methods_list(self) -> list[str]:
        return [m.strip() for m in self.allowed_withdrawal_methods.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def setup_logging(settings: Settings):
    """Configure application logging"""
    log_level = getattr(logging, settings.log_level)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
