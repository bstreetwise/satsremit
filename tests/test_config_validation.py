"""
Tests for src/core/config.py — secret validators.

We test the validator functions directly (not the full Settings class) to
avoid fighting pydantic-settings' env-var/file priority ordering.  This
is the correct unit-test approach: the validators are pure functions that
take a string and either return it or raise ValueError — test that contract.
"""

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Import the validator callables directly from the module-level constants
# so we can call them without instantiating Settings.
# ---------------------------------------------------------------------------

from src.core.config import (
    _PLACEHOLDER_SECRETS,
    _MIN_JWT_SECRET_LEN,
    _MIN_WEBHOOK_SECRET_LEN,
    Settings,
)


def _call_jwt_validator(value: str) -> str:
    """Call the jwt_secret_key field_validator directly."""
    return Settings.validate_jwt_secret_key(value)


def _call_webhook_validator(value: str) -> str:
    """Call the webhook_secret field_validator directly."""
    return Settings.validate_webhook_secret(value)


# ---------------------------------------------------------------------------
# JWT_SECRET_KEY validator
# ---------------------------------------------------------------------------

class TestJWTSecretKeyValidator:

    def test_strong_secret_accepted(self):
        v = "x" * 64
        assert _call_jwt_validator(v) == v

    def test_exact_minimum_length_accepted(self):
        v = "y" * _MIN_JWT_SECRET_LEN
        assert _call_jwt_validator(v) == v

    def test_one_below_minimum_rejected(self):
        with pytest.raises(ValueError, match="too short"):
            _call_jwt_validator("z" * (_MIN_JWT_SECRET_LEN - 1))

    def test_placeholder_value_rejected(self):
        with pytest.raises(ValueError, match="placeholder"):
            _call_jwt_validator("your-secret-key-change-in-production")

    def test_placeholder_case_insensitive(self):
        with pytest.raises(ValueError):
            _call_jwt_validator("Your-Secret-Key-Change-In-Production")

    def test_every_known_placeholder_rejected(self):
        for placeholder in _PLACEHOLDER_SECRETS:
            with pytest.raises(ValueError, match="placeholder"):
                _call_jwt_validator(placeholder)

    def test_error_message_contains_generation_command(self):
        with pytest.raises(ValueError) as exc_info:
            _call_jwt_validator("your-secret-key-change-in-production")
        assert "secrets.token_hex" in str(exc_info.value)

    def test_short_common_words_rejected(self):
        for weak in ["secret", "password", "changeme", "change-me", "example"]:
            with pytest.raises(ValueError):
                _call_jwt_validator(weak)

    def test_32_char_hex_accepted(self):
        import secrets
        v = secrets.token_hex(16)  # 32 hex chars
        assert _call_jwt_validator(v) == v

    def test_64_char_hex_accepted(self):
        import secrets
        v = secrets.token_hex(32)  # 64 hex chars
        assert _call_jwt_validator(v) == v


# ---------------------------------------------------------------------------
# WEBHOOK_SECRET validator
# ---------------------------------------------------------------------------

class TestWebhookSecretValidator:

    def test_strong_secret_accepted(self):
        v = "c" * 32
        assert _call_webhook_validator(v) == v

    def test_exact_minimum_length_accepted(self):
        v = "d" * _MIN_WEBHOOK_SECRET_LEN
        assert _call_webhook_validator(v) == v

    def test_one_below_minimum_rejected(self):
        with pytest.raises(ValueError, match="too short"):
            _call_webhook_validator("e" * (_MIN_WEBHOOK_SECRET_LEN - 1))

    def test_placeholder_rejected(self):
        with pytest.raises(ValueError, match="placeholder"):
            _call_webhook_validator("your-webhook-secret")

    def test_every_known_placeholder_rejected(self):
        for placeholder in _PLACEHOLDER_SECRETS:
            with pytest.raises(ValueError, match="placeholder"):
                _call_webhook_validator(placeholder)

    def test_short_common_words_rejected(self):
        for weak in ["placeholder", "replace-me", "todo", "secret"]:
            with pytest.raises(ValueError):
                _call_webhook_validator(weak)

    def test_random_token_accepted(self):
        import secrets
        v = secrets.token_hex(32)
        assert _call_webhook_validator(v) == v


# ---------------------------------------------------------------------------
# Production model_validator — tested via environment-variable injection
# since it runs at model level, not field level.
# We use monkeypatch to set os.environ so pydantic-settings picks them up,
# and clear lru_cache so get_settings() re-parses.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the lru_cache on get_settings before and after each test."""
    from src.core import config
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def _strong_env(monkeypatch, **overrides):
    """
    Inject a full set of strong env vars via monkeypatch so
    Settings() can be instantiated cleanly.
    """
    import secrets as sec
    from cryptography.fernet import Fernet

    base = {
        "DATABASE_URL": "postgresql://u:p@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "LND_REST_URL": "https://127.0.0.1:8080",
        "LND_MACAROON_PATH": "/tmp/admin.macaroon",
        "LND_CERT_PATH": "/tmp/tls.cert",
        "WHATSAPP_BUSINESS_ACCOUNT_ID": "test-account",
        "WHATSAPP_BUSINESS_PHONE_NUMBER_ID": "test-phone-id",
        "WHATSAPP_BUSINESS_ACCESS_TOKEN": "test-token",
        "JWT_SECRET_KEY": sec.token_hex(32),
        "WEBHOOK_SECRET": sec.token_hex(32),
        "PREIMAGE_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "ENVIRONMENT": "development",
        "DEBUG": "false",
    }
    base.update(overrides)
    for k, v in base.items():
        monkeypatch.setenv(k, str(v))


class TestProductionModelValidator:

    def test_production_without_preimage_key_rejected(self, monkeypatch):
        _strong_env(monkeypatch,
                    ENVIRONMENT="production",
                    PREIMAGE_ENCRYPTION_KEY="")
        with pytest.raises((ValidationError, ValueError)) as exc_info:
            Settings(_env_file=None)
        assert "PREIMAGE_ENCRYPTION_KEY" in str(exc_info.value)

    def test_production_with_debug_true_rejected(self, monkeypatch):
        from cryptography.fernet import Fernet
        _strong_env(monkeypatch,
                    ENVIRONMENT="production",
                    PREIMAGE_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                    DEBUG="true")
        with pytest.raises((ValidationError, ValueError)) as exc_info:
            Settings(_env_file=None)
        assert "DEBUG" in str(exc_info.value)

    def test_production_with_all_secrets_accepted(self, monkeypatch):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        _strong_env(monkeypatch,
                    ENVIRONMENT="production",
                    PREIMAGE_ENCRYPTION_KEY=key,
                    DEBUG="false")
        s = Settings(_env_file=None)
        assert s.is_production
        assert s.preimage_encryption_key == key

    def test_development_without_preimage_key_accepted(self, monkeypatch):
        _strong_env(monkeypatch, ENVIRONMENT="development", PREIMAGE_ENCRYPTION_KEY="")
        s = Settings(_env_file=None)
        assert not s.is_production

    def test_development_with_debug_true_accepted(self, monkeypatch):
        _strong_env(monkeypatch, ENVIRONMENT="development", DEBUG="true")
        s = Settings(_env_file=None)
        assert s.debug is True


# ---------------------------------------------------------------------------
# Placeholder set sanity checks
# ---------------------------------------------------------------------------

class TestPlaceholderSet:

    def test_known_bad_values_in_set(self):
        assert "your-secret-key-change-in-production" in _PLACEHOLDER_SECRETS
        assert "your-webhook-secret" in _PLACEHOLDER_SECRETS
        assert "secret" in _PLACEHOLDER_SECRETS
        assert "password" in _PLACEHOLDER_SECRETS
        assert "changeme" in _PLACEHOLDER_SECRETS

    def test_realistic_strong_secret_not_in_set(self):
        import secrets
        strong = secrets.token_hex(32)
        assert strong not in _PLACEHOLDER_SECRETS
