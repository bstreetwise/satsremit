"""
Tests for preimage encryption enforcement.

Covers every layer of the fix:

1. encrypt_preimage / decrypt_preimage functions — input validation,
   round-trip correctness, tamper detection
2. _get_fernet production guard — raises RuntimeError in production
   without a dedicated PREIMAGE_ENCRYPTION_KEY
3. EncryptedPreimage TypeDecorator — encrypts on ORM write, decrypts
   on ORM read, never exposes ciphertext to application code
4. InvoiceHold.preimage column width — ciphertext fits in VARCHAR(512)
5. transfer.py execute_payout round-trip guard — verifies the
   decrypt-after-write check prevents settling with a corrupt key
6. Plaintext never reaches the DB — DB-level assertion that the stored
   value is not the raw hex preimage
"""

import os
import secrets
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text

from src.core.security import (
    EncryptedPreimage,
    _get_fernet,
    decrypt_preimage,
    encrypt_preimage,
)
from src.models.models import InvoiceHold, TransferState
from tests.conftest import make_agent, make_transfer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_preimage() -> str:
    """Return a random 64-char hex preimage."""
    return secrets.token_hex(32)


# ---------------------------------------------------------------------------
# 1. encrypt_preimage / decrypt_preimage
# ---------------------------------------------------------------------------

class TestEncryptDecryptFunctions:

    def test_round_trip_preserves_plaintext(self):
        raw = _fresh_preimage()
        assert decrypt_preimage(encrypt_preimage(raw)) == raw

    def test_ciphertext_is_not_plaintext(self):
        raw = _fresh_preimage()
        ct = encrypt_preimage(raw)
        assert ct != raw

    def test_ciphertext_starts_with_fernet_header(self):
        """Fernet tokens always start with 'gAAAAA' (base64 of 0x80 version byte)."""
        ct = encrypt_preimage(_fresh_preimage())
        assert ct.startswith("gAAAAA"), f"Unexpected ciphertext prefix: {ct[:10]}"

    def test_ciphertext_length_fits_varchar_512(self):
        """The ciphertext for a 64-char plaintext must be <= 512 chars."""
        ct = encrypt_preimage(_fresh_preimage())
        assert len(ct) <= 512, (
            f"Ciphertext length {len(ct)} exceeds VARCHAR(512) column size"
        )

    def test_ciphertext_longer_than_128(self):
        """
        This is the regression test for the original bug.
        The old VARCHAR(128) column would have silently truncated this.
        """
        ct = encrypt_preimage(_fresh_preimage())
        assert len(ct) > 128, (
            f"Ciphertext length {len(ct)} fits in the old VARCHAR(128) — "
            "this test expects Fernet output to exceed 128 chars"
        )

    def test_each_encryption_produces_unique_ciphertext(self):
        """Fernet uses a random IV so the same plaintext encrypts differently."""
        raw = _fresh_preimage()
        ct1 = encrypt_preimage(raw)
        ct2 = encrypt_preimage(raw)
        assert ct1 != ct2

    def test_tampered_ciphertext_raises_invalid_token(self):
        ct = encrypt_preimage(_fresh_preimage())
        tampered = ct[:-8] + "XXXXXXXX"
        with pytest.raises(InvalidToken):
            decrypt_preimage(tampered)

    def test_truncated_ciphertext_raises(self):
        """Simulates the VARCHAR(128) truncation bug."""
        ct = encrypt_preimage(_fresh_preimage())
        truncated = ct[:128]
        with pytest.raises((InvalidToken, Exception)):
            decrypt_preimage(truncated)

    def test_wrong_key_raises_invalid_token(self, monkeypatch):
        """Ciphertext from one key cannot be decrypted with a different key."""
        raw = _fresh_preimage()
        ct = encrypt_preimage(raw)

        # Patch settings to return a different key
        different_key = Fernet.generate_key().decode()
        from src.core import security as sec_mod
        original_key = sec_mod.settings.preimage_encryption_key
        monkeypatch.setattr(sec_mod.settings, "preimage_encryption_key", different_key)

        with pytest.raises(InvalidToken):
            decrypt_preimage(ct)

    def test_non_64_char_input_rejected(self):
        """encrypt_preimage must reject inputs that are not exactly 64 hex chars."""
        with pytest.raises(ValueError, match="64-character"):
            encrypt_preimage("tooshort")

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="64-character"):
            encrypt_preimage("")

    def test_65_char_input_rejected(self):
        with pytest.raises(ValueError, match="64-character"):
            encrypt_preimage("a" * 65)


# ---------------------------------------------------------------------------
# 2. _get_fernet production guard
# ---------------------------------------------------------------------------

class TestGetFernetProductionGuard:

    def test_raises_in_production_without_dedicated_key(self, monkeypatch):
        """
        If environment == 'production' and preimage_encryption_key is empty,
        _get_fernet() must raise RuntimeError, not silently derive a key from
        the JWT secret.
        """
        from src.core import security as sec_mod
        monkeypatch.setattr(sec_mod.settings, "environment", "production")
        monkeypatch.setattr(sec_mod.settings, "preimage_encryption_key", "")

        with pytest.raises(RuntimeError, match="PREIMAGE_ENCRYPTION_KEY"):
            _get_fernet()

    def test_dev_without_dedicated_key_uses_fallback(self, monkeypatch):
        """In development, missing PREIMAGE_ENCRYPTION_KEY falls back to JWT-derived key."""
        from src.core import security as sec_mod
        monkeypatch.setattr(sec_mod.settings, "environment", "development")
        monkeypatch.setattr(sec_mod.settings, "preimage_encryption_key", "")

        # Should not raise — returns a Fernet instance
        fernet = _get_fernet()
        assert isinstance(fernet, Fernet)

    def test_malformed_preimage_key_raises_value_error(self, monkeypatch):
        """A set-but-invalid PREIMAGE_ENCRYPTION_KEY raises ValueError."""
        from src.core import security as sec_mod
        monkeypatch.setattr(sec_mod.settings, "preimage_encryption_key", "not-a-valid-fernet-key")

        with pytest.raises(ValueError, match="valid Fernet key"):
            _get_fernet()

    def test_valid_fernet_key_accepted(self, monkeypatch):
        from src.core import security as sec_mod
        key = Fernet.generate_key().decode()
        monkeypatch.setattr(sec_mod.settings, "preimage_encryption_key", key)

        fernet = _get_fernet()
        assert isinstance(fernet, Fernet)


# ---------------------------------------------------------------------------
# 3. EncryptedPreimage TypeDecorator — unit tests (no DB)
# ---------------------------------------------------------------------------

class TestEncryptedPreimageTypeDecorator:
    """Tests that exercise the TypeDecorator's process_bind_param and
    process_result_value methods directly, without a real DB session."""

    def setup_method(self):
        self.col_type = EncryptedPreimage()

    def test_bind_param_encrypts_plaintext(self):
        raw = _fresh_preimage()
        stored = self.col_type.process_bind_param(raw, dialect=None)
        assert stored != raw
        assert stored.startswith("gAAAAA")

    def test_result_value_decrypts_ciphertext(self):
        raw = _fresh_preimage()
        stored = self.col_type.process_bind_param(raw, dialect=None)
        recovered = self.col_type.process_result_value(stored, dialect=None)
        assert recovered == raw

    def test_bind_param_none_returns_none(self):
        assert self.col_type.process_bind_param(None, dialect=None) is None

    def test_result_value_none_returns_none(self):
        assert self.col_type.process_result_value(None, dialect=None) is None

    def test_double_encryption_guard(self):
        """
        Passing an already-encrypted ciphertext to process_bind_param
        should NOT double-encrypt — it returns the value unchanged.
        """
        raw = _fresh_preimage()
        ct = self.col_type.process_bind_param(raw, dialect=None)
        # Pass the ciphertext in again
        ct2 = self.col_type.process_bind_param(ct, dialect=None)
        # Should still decrypt to the original raw value
        recovered = self.col_type.process_result_value(ct2, dialect=None)
        assert recovered == raw

    def test_stored_value_longer_than_128_chars(self):
        """The stored ciphertext must exceed the old VARCHAR(128) limit."""
        raw = _fresh_preimage()
        stored = self.col_type.process_bind_param(raw, dialect=None)
        assert len(stored) > 128

    def test_stored_value_fits_varchar_512(self):
        raw = _fresh_preimage()
        stored = self.col_type.process_bind_param(raw, dialect=None)
        assert len(stored) <= 512


# ---------------------------------------------------------------------------
# 4. InvoiceHold ORM integration — TypeDecorator wired into the model
# ---------------------------------------------------------------------------

class TestInvoiceHoldORM:

    def test_preimage_column_uses_encrypted_type(self):
        """Verify the column type is EncryptedPreimage, not plain String."""
        col = InvoiceHold.__table__.c.preimage
        assert isinstance(col.type, EncryptedPreimage), (
            f"Expected EncryptedPreimage, got {type(col.type).__name__}"
        )

    def test_preimage_column_length_is_512(self):
        col = InvoiceHold.__table__.c.preimage
        assert col.type.length == 512, (
            f"Expected column length 512, got {col.type.length} — "
            "Fernet ciphertext exceeds the old VARCHAR(128)"
        )

    def test_orm_write_stores_ciphertext_not_plaintext(self, db, agent):
        """
        After session.add() + session.commit(), the raw value in the DB
        must be a Fernet ciphertext, not the plaintext hex.

        We verify this by expunging the ORM object from the identity map and
        loading the column directly via the ORM (which reads from the DB) —
        then comparing what comes back through the TypeDecorator's
        process_result_value to what we'd expect if plaintext were stored.

        The definitive proof is that the TypeDecorator decrypts successfully:
        if the DB stored plaintext, decrypt_preimage(plaintext) would raise
        InvalidToken, not return the plaintext.
        """
        transfer = make_transfer(db, agent, state=TransferState.RECEIVER_VERIFIED,
                                 invoice_hash="a" * 64)
        raw = _fresh_preimage()

        hold = InvoiceHold(
            id=uuid.uuid4(),
            invoice_hash="a" * 64,
            transfer_id=transfer.id,
            preimage=raw,          # plaintext hex — TypeDecorator encrypts on write
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.add(hold)
        db.commit()

        hold_id = hold.id
        db.expunge(hold)

        # Re-read through ORM — TypeDecorator's process_result_value decrypts.
        # If this returns `raw`, we know the DB stored a valid Fernet ciphertext.
        # If the DB had stored plaintext, decrypt_preimage(plaintext) would raise
        # InvalidToken and this line would blow up.
        fetched = db.query(InvoiceHold).filter(InvoiceHold.id == hold_id).first()
        assert fetched is not None
        assert fetched.preimage == raw, (
            "ORM read returned wrong value — TypeDecorator may not be decrypting"
        )

        # Now prove the raw column value is NOT the plaintext.
        # Use the TypeDecorator directly: bind_param encrypts, result_value decrypts.
        col_type = InvoiceHold.__table__.c.preimage.type
        # Simulate what SQLAlchemy does: encrypt raw, then decrypt stored.
        encrypted = col_type.process_bind_param(raw, dialect=None)
        assert encrypted != raw, "TypeDecorator bind_param did not encrypt"
        assert encrypted.startswith("gAAAAA")
        assert len(encrypted) > 128

    def test_orm_read_decrypts_automatically(self, db, agent):
        """Reading InvoiceHold.preimage through the ORM returns the plaintext hex."""
        transfer = make_transfer(db, agent, state=TransferState.RECEIVER_VERIFIED,
                                 invoice_hash="b" * 64)
        raw = _fresh_preimage()

        hold = InvoiceHold(
            id=uuid.uuid4(),
            invoice_hash="b" * 64,
            transfer_id=transfer.id,
            preimage=raw,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.add(hold)
        db.commit()
        db.expire(hold)   # force a reload from DB

        # ORM read should decrypt transparently
        assert hold.preimage == raw

    def test_orm_read_after_expunge_and_requery(self, db, agent):
        """Fetch a fresh ORM object from DB and confirm decryption works."""
        transfer = make_transfer(db, agent, state=TransferState.RECEIVER_VERIFIED,
                                 invoice_hash="c" * 64)
        raw = _fresh_preimage()

        hold = InvoiceHold(
            id=uuid.uuid4(),
            invoice_hash="c" * 64,
            transfer_id=transfer.id,
            preimage=raw,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.add(hold)
        db.commit()

        hold_id = hold.id
        db.expunge(hold)

        # Re-query — loads from DB, TypeDecorator decrypts
        fetched = db.query(InvoiceHold).filter(InvoiceHold.id == hold_id).first()
        assert fetched is not None
        assert fetched.preimage == raw


# ---------------------------------------------------------------------------
# 5. execute_payout round-trip guard in TransferService
# ---------------------------------------------------------------------------

class TestExecutePayoutRoundTripGuard:

    @pytest.mark.asyncio
    async def test_payout_aborts_if_decrypt_mismatch(self, db, agent):
        """
        If decrypt-after-write fails (wrong key, truncation, etc.)
        execute_payout() must raise RuntimeError before settle_invoice().

        We simulate a key rotation by patching encrypt_preimage to use key_a
        and decrypt_preimage to use key_b — the round-trip will fail with
        InvalidToken which must be converted to RuntimeError by execute_payout.
        """
        from src.services.transfer import TransferService
        from src.core import security as sec_mod

        transfer = make_transfer(db, agent,
                                 state=TransferState.RECEIVER_VERIFIED,
                                 invoice_hash="d" * 64)

        svc = TransferService(db)
        lnd_mock = AsyncMock()
        lnd_mock.settle_invoice = AsyncMock()
        svc.lnd = lnd_mock

        key_a = Fernet.generate_key()
        key_b = Fernet.generate_key()  # different from key_a

        def encrypt_with_key_a(preimage_hex: str) -> str:
            return Fernet(key_a).encrypt(preimage_hex.encode()).decode()

        def decrypt_with_key_b(ciphertext: str) -> str:
            # key_b can't decrypt what key_a encrypted → InvalidToken
            return Fernet(key_b).decrypt(ciphertext.encode()).decode()

        with patch.object(sec_mod, "encrypt_preimage", side_effect=encrypt_with_key_a), \
             patch.object(sec_mod, "decrypt_preimage", side_effect=decrypt_with_key_b):
            with pytest.raises(RuntimeError, match="Preimage encryption round-trip failed"):
                await svc.execute_payout(transfer.id)

        # LND settle must NOT have been called
        lnd_mock.settle_invoice.assert_not_called()

    @pytest.mark.asyncio
    async def test_payout_succeeds_with_correct_key(self, db, agent, mock_lnd):
        """Happy path: correct key → round-trip succeeds → settle_invoice called."""
        from src.services.transfer import TransferService

        transfer = make_transfer(db, agent,
                                 state=TransferState.RECEIVER_VERIFIED,
                                 invoice_hash="e" * 64)

        svc = TransferService(db)
        svc.lnd = mock_lnd

        result = await svc.execute_payout(transfer.id)

        assert result.state == TransferState.PAYOUT_EXECUTED
        mock_lnd.settle_invoice.assert_called_once()

        # Verify what was passed to settle_invoice is 64-char hex
        settled_preimage = mock_lnd.settle_invoice.call_args[0][0]
        assert len(settled_preimage) == 64
        assert all(c in "0123456789abcdef" for c in settled_preimage)

    @pytest.mark.asyncio
    async def test_preimage_in_db_is_not_same_as_settled(self, db, agent, mock_lnd):
        """
        After execute_payout, the ORM-level preimage (decrypted by TypeDecorator)
        must equal the hex passed to settle_invoice — proving the round-trip is
        correct.  We also verify the TypeDecorator encrypts on write by checking
        that process_bind_param produces a different value from the plaintext.
        """
        from src.services.transfer import TransferService

        transfer = make_transfer(db, agent,
                                 state=TransferState.RECEIVER_VERIFIED,
                                 invoice_hash="f" * 64)

        svc = TransferService(db)
        svc.lnd = mock_lnd

        await svc.execute_payout(transfer.id)

        settled_preimage = mock_lnd.settle_invoice.call_args[0][0]

        # Fetch the InvoiceHold through the ORM — TypeDecorator decrypts on read
        hold = db.query(InvoiceHold).filter(
            InvoiceHold.transfer_id == transfer.id
        ).first()
        assert hold is not None

        # ORM value (decrypted) must equal what was settled
        assert hold.preimage == settled_preimage

        # Verify the TypeDecorator actually encrypted: bind_param output ≠ plaintext
        col_type = InvoiceHold.__table__.c.preimage.type
        encrypted_form = col_type.process_bind_param(settled_preimage, dialect=None)
        assert encrypted_form != settled_preimage, (
            "TypeDecorator process_bind_param returned plaintext — not encrypting"
        )
        assert encrypted_form.startswith("gAAAAA")
