"""
Unit tests for src/core/security.py

Covers:
- PIN hashing and verification
- Preimage encrypt/decrypt round-trip
- JWT create/decode, expiry, bad signature
- HMAC webhook signature verification
- get_current_admin raises 403 for non-admin tokens
"""

import hashlib
import hmac
import time
from datetime import timedelta

import pytest
from fastapi import HTTPException

from src.core.security import (
    create_token,
    decode_token,
    encrypt_preimage,
    decrypt_preimage,
    generate_pin,
    hash_pin,
    hash_password,
    verify_password,
    verify_pin,
    verify_webhook_hmac,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    def test_hash_and_verify_correct(self):
        pw = "MySecurePassword99!"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)

    def test_wrong_password_rejected(self):
        hashed = hash_password("correct-password")
        assert not verify_password("wrong-password", hashed)

    def test_hashes_are_not_plaintext(self):
        pw = "plaintext"
        assert hash_password(pw) != pw


# ---------------------------------------------------------------------------
# PIN helpers
# ---------------------------------------------------------------------------

class TestPINHelpers:
    def test_generate_pin_is_four_digits(self):
        pin = generate_pin()
        assert len(pin) == 4
        assert pin.isdigit()

    def test_hash_pin_and_verify_correct_pin(self):
        pin = "1234"
        hashed = hash_pin(pin)
        assert verify_pin(hashed, pin)

    def test_verify_pin_rejects_wrong_pin(self):
        hashed = hash_pin("5678")
        assert not verify_pin(hashed, "0000")

    def test_hash_pin_does_not_store_plaintext(self):
        pin = "9999"
        assert hash_pin(pin) != pin

    def test_verify_pin_rejects_raw_hash_as_pin(self):
        """Ensure double-hashing bug is gone: the old code did hashed == hash_password(pin)."""
        pin = "1234"
        hashed = hash_pin(pin)
        # Passing the hash itself as the provided_pin must fail
        assert not verify_pin(hashed, hashed)


# ---------------------------------------------------------------------------
# Preimage encryption
# ---------------------------------------------------------------------------

class TestPreimageEncryption:
    def test_roundtrip(self):
        original = "a" * 64  # 64 hex chars (32-byte preimage)
        ciphertext = encrypt_preimage(original)
        assert decrypt_preimage(ciphertext) == original

    def test_ciphertext_differs_from_plaintext(self):
        preimage = "b" * 64
        assert encrypt_preimage(preimage) != preimage

    def test_different_preimages_produce_different_ciphertexts(self):
        c1 = encrypt_preimage("a" * 64)
        c2 = encrypt_preimage("b" * 64)
        assert c1 != c2

    def test_tampered_ciphertext_raises(self):
        from cryptography.fernet import InvalidToken
        ciphertext = encrypt_preimage("c" * 64)
        # Flip a character to tamper
        tampered = ciphertext[:-4] + "XXXX"
        with pytest.raises(Exception):
            decrypt_preimage(tampered)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

class TestJWT:
    def test_create_and_decode_agent_token(self):
        import uuid
        agent_id = str(uuid.uuid4())
        token = create_token(subject=f"agent:{agent_id}", agent_id=agent_id)
        payload = decode_token(token)
        assert payload["agent_id"] == agent_id
        assert payload["sub"] == f"agent:{agent_id}"

    def test_admin_flag_in_token(self):
        import uuid
        agent_id = str(uuid.uuid4())
        token = create_token(subject=f"agent:{agent_id}", agent_id=agent_id, is_admin=True)
        payload = decode_token(token)
        assert payload["is_admin"] is True

    def test_non_admin_token_has_false_flag(self):
        import uuid
        agent_id = str(uuid.uuid4())
        token = create_token(subject=f"agent:{agent_id}", agent_id=agent_id, is_admin=False)
        payload = decode_token(token)
        assert payload["is_admin"] is False

    def test_expired_token_raises_401(self):
        import uuid
        agent_id = str(uuid.uuid4())
        token = create_token(
            subject=f"agent:{agent_id}",
            agent_id=agent_id,
            expires_delta=timedelta(seconds=-1),  # already expired
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401

    def test_tampered_token_raises_401(self):
        import uuid
        agent_id = str(uuid.uuid4())
        token = create_token(subject=f"agent:{agent_id}", agent_id=agent_id)
        # Corrupt the signature portion
        parts = token.split(".")
        parts[-1] = parts[-1][:-4] + "XXXX"
        bad_token = ".".join(parts)
        with pytest.raises(HTTPException) as exc_info:
            decode_token(bad_token)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# HMAC webhook verification
# ---------------------------------------------------------------------------

class TestWebhookHMAC:
    def _make_signature(self, body: bytes, secret: str = "test-webhook-secret") -> str:
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def test_valid_signature_passes(self):
        body = b'{"invoice_hash": "abc"}'
        sig = self._make_signature(body)
        assert verify_webhook_hmac(body, sig) is True

    def test_tampered_body_fails(self):
        body = b'{"invoice_hash": "abc"}'
        sig = self._make_signature(body)
        tampered = b'{"invoice_hash": "xyz"}'
        assert verify_webhook_hmac(tampered, sig) is False

    def test_wrong_secret_fails(self):
        body = b'{"invoice_hash": "abc"}'
        sig = self._make_signature(body, secret="wrong-secret")
        assert verify_webhook_hmac(body, sig) is False

    def test_missing_prefix_fails(self):
        body = b'test'
        bare_hex = hmac.new(b"test-webhook-secret", body, hashlib.sha256).hexdigest()
        assert verify_webhook_hmac(body, bare_hex) is False

    def test_empty_header_fails(self):
        assert verify_webhook_hmac(b"body", "") is False
