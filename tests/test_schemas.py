"""
Unit tests for Pydantic schema validators (src/api/schemas.py).

Covers:
- Phone number validator: valid E.164, digits-with-dashes, invalid with letters
- Amount validator: below minimum, above maximum, valid range
- TransferCreateRequest field constraints
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.api.schemas import TransferCreateRequest


# ---------------------------------------------------------------------------
# Phone validator
# ---------------------------------------------------------------------------

class TestPhoneValidator:
    """Tests for the @field_validator on sender_phone / receiver_phone."""

    BASE = dict(
        receiver_phone="+263771234567",
        receiver_name="Jane Doe",
        receiver_location="ZWE_HRR",
        amount_zar=Decimal("200.00"),
    )

    def test_e164_format_accepted(self):
        data = {**self.BASE, "sender_phone": "+27821234567"}
        req = TransferCreateRequest(**data)
        assert req.sender_phone == "+27821234567"

    def test_digits_with_dashes_accepted(self):
        data = {**self.BASE, "sender_phone": "27-82-123-4567"}
        req = TransferCreateRequest(**data)
        assert req.sender_phone == "27-82-123-4567"

    def test_digits_with_spaces_accepted(self):
        data = {**self.BASE, "sender_phone": "27 82 123 4567"}
        req = TransferCreateRequest(**data)
        assert req.sender_phone == "27 82 123 4567"

    def test_letters_in_phone_rejected(self):
        data = {**self.BASE, "sender_phone": "+27abc123456"}
        with pytest.raises(ValidationError) as exc_info:
            TransferCreateRequest(**data)
        errors = exc_info.value.errors()
        assert any("phone" in str(e).lower() or "Invalid" in str(e) for e in errors)

    def test_receiver_phone_validated_too(self):
        data = {**self.BASE, "sender_phone": "+27821234567", "receiver_phone": "notaphone!!"}
        with pytest.raises(ValidationError):
            TransferCreateRequest(**data)

    def test_both_phones_validated(self):
        data = {**self.BASE, "sender_phone": "bad!", "receiver_phone": "alsobad!"}
        with pytest.raises(ValidationError):
            TransferCreateRequest(**data)


# ---------------------------------------------------------------------------
# Amount validator (defined in models/schemas.py CreateTransferRequest)
# ---------------------------------------------------------------------------

class TestAmountValidator:
    """
    TransferCreateRequest uses Pydantic's gt=0 constraint plus the
    field_validator in models/schemas.py checks 100–500 range.

    src/api/schemas.py TransferCreateRequest uses decimal_places=2 + gt=0.
    The min/max is enforced by rate_svc.validate_transfer_amount at runtime,
    not at schema parse time.  Test what the schema itself enforces.
    """

    BASE = dict(
        sender_phone="+27821234567",
        receiver_phone="+263771234567",
        receiver_name="Jane Doe",
        receiver_location="ZWE_HRR",
    )

    def test_positive_amount_accepted(self):
        data = {**self.BASE, "amount_zar": Decimal("200.00")}
        req = TransferCreateRequest(**data)
        assert req.amount_zar == Decimal("200.00")

    def test_zero_amount_rejected(self):
        data = {**self.BASE, "amount_zar": Decimal("0")}
        with pytest.raises(ValidationError):
            TransferCreateRequest(**data)

    def test_negative_amount_rejected(self):
        data = {**self.BASE, "amount_zar": Decimal("-50")}
        with pytest.raises(ValidationError):
            TransferCreateRequest(**data)

    def test_fractional_amount_accepted(self):
        data = {**self.BASE, "amount_zar": Decimal("150.50")}
        req = TransferCreateRequest(**data)
        assert req.amount_zar == Decimal("150.50")


# ---------------------------------------------------------------------------
# models/schemas.py CreateTransferRequest — range validator
# ---------------------------------------------------------------------------

class TestModelsSchemaAmountValidator:
    """Tests for CreateTransferRequest in src/models/schemas.py which
    enforces the 100–500 ZAR range via @validator."""

    from src.models.schemas import CreateTransferRequest

    BASE = dict(
        sender_phone="+27821234567",
        receiver_phone="+263771234567",
        receiver_name="Jane Doe",
        location_code="ZWE_HRR",
    )

    def test_below_minimum_rejected(self):
        from src.models.schemas import CreateTransferRequest
        data = {**self.BASE, "amount_zar": Decimal("50")}
        with pytest.raises(ValidationError) as exc_info:
            CreateTransferRequest(**data)
        assert "100" in str(exc_info.value)

    def test_above_maximum_rejected(self):
        from src.models.schemas import CreateTransferRequest
        data = {**self.BASE, "amount_zar": Decimal("600")}
        with pytest.raises(ValidationError) as exc_info:
            CreateTransferRequest(**data)
        assert "500" in str(exc_info.value)

    def test_boundary_minimum_accepted(self):
        from src.models.schemas import CreateTransferRequest
        data = {**self.BASE, "amount_zar": Decimal("100")}
        req = CreateTransferRequest(**data)
        assert req.amount_zar == Decimal("100")

    def test_boundary_maximum_accepted(self):
        from src.models.schemas import CreateTransferRequest
        data = {**self.BASE, "amount_zar": Decimal("500")}
        req = CreateTransferRequest(**data)
        assert req.amount_zar == Decimal("500")


# ---------------------------------------------------------------------------
# Receiver name constraints
# ---------------------------------------------------------------------------

class TestReceiverName:
    BASE = dict(
        sender_phone="+27821234567",
        receiver_phone="+263771234567",
        receiver_location="ZWE_HRR",
        amount_zar=Decimal("200.00"),
    )

    def test_name_too_short_rejected(self):
        data = {**self.BASE, "receiver_name": "A"}  # min_length=2
        with pytest.raises(ValidationError):
            TransferCreateRequest(**data)

    def test_name_too_long_rejected(self):
        data = {**self.BASE, "receiver_name": "A" * 101}  # max_length=100
        with pytest.raises(ValidationError):
            TransferCreateRequest(**data)

    def test_valid_name_accepted(self):
        data = {**self.BASE, "receiver_name": "Jane Doe"}
        req = TransferCreateRequest(**data)
        assert req.receiver_name == "Jane Doe"
