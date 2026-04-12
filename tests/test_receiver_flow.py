"""
Test suite for receiver verification flow
Tests PIN generation, verification, and resend functionality
"""

import pytest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import create_app
from src.models.models import Transfer, TransferState, Agent, AgentStatus
from src.core.security import generate_pin, hash_pin, verify_pin
from src.db.database import SessionLocal


@pytest.fixture
def app():
    """Create test app instance"""
    app = create_app()
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def db():
    """Create test database session"""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def test_agent(db):
    """Create test agent"""
    agent = Agent(
        id=uuid.uuid4(),
        phone="+27123456789",
        name="Test Agent",
        email="agent@test.com",
        password_hash="hashed",
        location_code="ZWE_HRR",
        location_name="Harare",
        cash_balance_zar=Decimal("10000.00"),
        commission_balance_sats=0,
        status=AgentStatus.ACTIVE,
        is_admin=False,
    )
    db.add(agent)
    db.commit()
    return agent


@pytest.fixture
def test_transfer(db, test_agent):
    """Create test transfer"""
    transfer = Transfer(
        id=uuid.uuid4(),
        reference="TEST1234567890",
        sender_phone="+27987654321",
        receiver_phone="+27111111111",
        receiver_name="Test Receiver",
        receiver_location="ZWE_HRR",
        agent_id=test_agent.id,
        amount_zar=Decimal("500.00"),
        amount_sats=1000,
        rate_zar_per_btc=Decimal("2000000.00"),
        invoice_hash="test_hash_123",
        payment_request="lnbc...",
        invoice_expiry_at=datetime.utcnow() + timedelta(minutes=30),
        state=TransferState.PAYMENT_LOCKED,
        receiver_phone_verified=False,
        agent_verified=False,
        created_at=datetime.utcnow(),
        paid_at=datetime.utcnow(),
    )
    
    # Generate and hash a PIN
    pin = generate_pin()
    transfer.pin_generated = hash_pin(pin)
    
    db.add(transfer)
    db.commit()
    
    return transfer, pin


class TestReceiverFlowEndpoints:
    """Test receiver verification endpoints"""
    
    def test_get_transfer_status_with_valid_reference(self, client, test_transfer):
        """Test receiver can get transfer status with reference and phone"""
        transfer, _ = test_transfer
        
        response = client.get(
            f"/api/receivers/transfers/{transfer.reference}/status",
            params={"phone": transfer.receiver_phone}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["reference"] == transfer.reference
        assert data["receiver_name"] == transfer.receiver_name
        assert data["amount_zar"] == float(transfer.amount_zar)
    
    def test_get_transfer_status_not_found(self, client):
        """Test 404 when transfer not found"""
        response = client.get(
            "/api/receivers/transfers/INVALID/status",
            params={"phone": "+27123456789"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_get_transfer_status_phone_mismatch(self, client, test_transfer):
        """Test 404 when phone doesn't match receiver"""
        transfer, _ = test_transfer
        
        response = client.get(
            f"/api/receivers/transfers/{transfer.reference}/status",
            params={"phone": "+27999999999"}  # Wrong phone
        )
        
        assert response.status_code == 404
    
    def test_verify_pin_success(self, client, test_transfer, db):
        """Test successful PIN verification"""
        transfer, pin = test_transfer
        
        response = client.post(
            "/api/receivers/verify-pin",
            json={
                "reference": transfer.reference,
                "phone": transfer.receiver_phone,
                "pin": pin,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert data["receiver_name"] == transfer.receiver_name
        
        # Verify transfer state updated
        db.refresh(transfer)
        assert transfer.receiver_phone_verified is True
    
    def test_verify_pin_invalid(self, client, test_transfer):
        """Test PIN verification with wrong PIN"""
        transfer, _ = test_transfer
        
        response = client.post(
            "/api/receivers/verify-pin",
            json={
                "reference": transfer.reference,
                "phone": transfer.receiver_phone,
                "pin": "9999",  # Wrong PIN
            }
        )
        
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()
    
    def test_verify_pin_already_verified(self, client, test_transfer, db):
        """Test verification when already verified"""
        transfer, _ = test_transfer
        transfer.receiver_phone_verified = True
        db.commit()
        
        response = client.post(
            "/api/receivers/verify-pin",
            json={
                "reference": transfer.reference,
                "phone": transfer.receiver_phone,
                "pin": "1234",
            }
        )
        
        assert response.status_code == 200
        assert "already verified" in response.json()["message"].lower()
    
    def test_verify_pin_wrong_transfer_state(self, client, test_transfer, db):
        """Test PIN verification fails if transfer not in PAYMENT_LOCKED state"""
        transfer, pin = test_transfer
        transfer.state = TransferState.INITIATED  # Wrong state
        db.commit()
        
        response = client.post(
            "/api/receivers/verify-pin",
            json={
                "reference": transfer.reference,
                "phone": transfer.receiver_phone,
                "pin": pin,
            }
        )
        
        assert response.status_code == 400
        assert "cannot verify" in response.json()["detail"].lower()
    
    def test_resend_pin_success(self, client, test_transfer):
        """Test successful PIN resend"""
        transfer, _ = test_transfer
        
        response = client.post(
            "/api/receivers/resend-pin",
            json={
                "reference": transfer.reference,
                "phone": transfer.receiver_phone,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["next_resend_in_seconds"] == 300
    
    def test_resend_pin_rate_limit(self, client, test_transfer, db):
        """Test PIN resend rate limiting"""
        transfer, _ = test_transfer
        transfer.last_pin_resent_at = datetime.utcnow() - timedelta(seconds=60)
        db.commit()
        
        response = client.post(
            "/api/receivers/resend-pin",
            json={
                "reference": transfer.reference,
                "phone": transfer.receiver_phone,
            }
        )
        
        assert response.status_code == 429
        assert "wait" in response.json()["detail"].lower()
    
    def test_resend_pin_already_verified(self, client, test_transfer, db):
        """Test resend fails if already verified"""
        transfer, _ = test_transfer
        transfer.receiver_phone_verified = True
        db.commit()
        
        response = client.post(
            "/api/receivers/resend-pin",
            json={
                "reference": transfer.reference,
                "phone": transfer.receiver_phone,
            }
        )
        
        assert response.status_code == 400
        assert "already verified" in response.json()["detail"].lower()


class TestPINGeneration:
    """Test PIN generation and verification"""
    
    def test_generate_pin_format(self):
        """Test PIN is 4-digit string"""
        pin = generate_pin()
        assert len(pin) == 4
        assert pin.isdigit()
    
    def test_pin_hash_security(self):
        """Test PIN hashing is secure (not plaintext)"""
        pin = "1234"
        hashed = hash_pin(pin)
        assert hashed != pin
        assert len(hashed) > len(pin)
    
    def test_pin_verification_correct(self):
        """Test correct PIN verifies"""
        pin = "5678"
        hashed = hash_pin(pin)
        assert verify_pin(hashed, pin) is True
    
    def test_pin_verification_incorrect(self):
        """Test incorrect PIN doesn't verify"""
        pin = "5678"
        hashed = hash_pin(pin)
        assert verify_pin(hashed, "9999") is False


class TestReceiverDualVerification:
    """Test receiver + agent dual verification workflow"""
    
    def test_transition_to_receiver_verified_both_verified(self, client, test_transfer, db):
        """Test state transitions to RECEIVER_VERIFIED when both verified"""
        transfer, pin = test_transfer
        transfer.agent_verified = True  # Agent already verified
        db.commit()
        
        response = client.post(
            "/api/receivers/verify-pin",
            json={
                "reference": transfer.reference,
                "phone": transfer.receiver_phone,
                "pin": pin,
            }
        )
        
        assert response.status_code == 200
        
        # Check state changed
        db.refresh(transfer)
        assert transfer.state == TransferState.RECEIVER_VERIFIED
    
    def test_no_transition_when_agent_not_verified(self, client, test_transfer, db):
        """Test state doesn't change to RECEIVER_VERIFIED if agent not verified"""
        transfer, pin = test_transfer
        transfer.agent_verified = False  # Agent not verified
        db.commit()
        
        response = client.post(
            "/api/receivers/verify-pin",
            json={
                "reference": transfer.reference,
                "phone": transfer.receiver_phone,
                "pin": pin,
            }
        )
        
        assert response.status_code == 200
        
        # Check state didn't change
        db.refresh(transfer)
        assert transfer.state == TransferState.PAYMENT_LOCKED
