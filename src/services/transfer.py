"""
Transfer Service - Main business logic for remittance transfers
Orchestrates transfer lifecycle: invoice creation, payment verification, settlement
"""

import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from decimal import Decimal
from enum import Enum
import uuid

from sqlalchemy.orm import Session

from src.models.models import (
    Transfer,
    TransferState,
    TransferHistory,
    InvoiceHold,
    Agent,
)
from src.services.lnd import LNDService
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class TransferService:
    """Manage transfer lifecycle and state machine"""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.lnd = LNDService()
        self.invoice_timeout_hours = self.settings.lnd_invoice_timeout_hours
        self.verification_timeout = self.settings.verification_timeout_minutes

    def _generate_reference(self) -> str:
        """Generate unique transfer reference (20 chars)"""
        timestamp = datetime.utcnow().strftime("%y%m%d%H%M%S")  # 12 chars
        random_suffix = secrets.token_hex(4)  # 8 chars
        return f"{timestamp}{random_suffix}"

    def _hash_phone(self, phone: str) -> str:
        """Hash phone number for privacy"""
        return hashlib.sha256(phone.encode()).hexdigest()[:16]

    async def initiate_transfer(
        self,
        sender_phone: str,
        receiver_phone: str,
        receiver_name: str,
        receiver_location: str,
        amount_zar: Decimal,
        amount_sats: int,
        rate_zar_per_btc: Decimal,
        agent_id: uuid.UUID,
    ) -> Transfer:
        """
        Initiate a new transfer

        Args:
            sender_phone: Sender phone number
            receiver_phone: Receiver phone number
            receiver_name: Receiver full name
            receiver_location: Receiver location code
            amount_zar: Amount in ZAR
            amount_sats: Amount in satoshis
            rate_zar_per_btc: Exchange rate at time of transfer
            agent_id: Agent handling the payout

        Returns:
            Created Transfer object
        """
        try:
            # Validate agent exists and is active
            agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")
            if agent.status.value != "ACTIVE":
                raise ValueError(f"Agent {agent_id} is not active")

            # Create transfer record
            transfer = Transfer(
                id=uuid.uuid4(),
                reference=self._generate_reference(),
                sender_phone=sender_phone,
                receiver_phone=receiver_phone,
                receiver_name=receiver_name,
                receiver_location=receiver_location,
                amount_zar=amount_zar,
                amount_sats=amount_sats,
                rate_zar_per_btc=rate_zar_per_btc,
                agent_id=agent_id,
                state=TransferState.INITIATED,
            )

            self.db.add(transfer)
            self.db.commit()

            # Log state change
            self._log_state_change(
                transfer.id,
                old_state=None,
                new_state=TransferState.INITIATED,
                reason="Transfer initiated by sender",
                actor_type="sender",
            )

            logger.info(f"Transfer initiated: {transfer.reference} ({transfer.id})")
            return transfer

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to initiate transfer: {e}")
            raise

    async def generate_invoice(
        self,
        transfer_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Generate LND hold invoice for transfer

        Args:
            transfer_id: Transfer ID

        Returns:
            {
                "payment_hash": "...",
                "payment_request": "lnbc...",
                "invoice_expiry_at": datetime,
            }
        """
        try:
            transfer = self.db.query(Transfer).filter(
                Transfer.id == transfer_id
            ).first()

            if not transfer:
                raise ValueError(f"Transfer {transfer_id} not found")

            if transfer.state not in [TransferState.INITIATED, TransferState.INVOICE_GENERATED]:
                raise ValueError(
                    f"Cannot generate invoice for transfer in state {transfer.state}"
                )

            # Create memo with reference
            memo = f"SatsRemit: {transfer.reference}"

            # Create hold invoice via LND
            invoice = await self.lnd.create_hold_invoice(
                amount_sats=transfer.amount_sats,
                memo=memo,
            )

            # Store invoice details
            payment_hash = invoice["payment_hash"]
            expiry_at = datetime.utcnow() + timedelta(
                minutes=self.settings.lnd_hold_invoice_expiry_minutes
            )

            transfer.invoice_hash = payment_hash
            transfer.payment_request = invoice["payment_request"]
            transfer.invoice_expiry_at = expiry_at
            transfer.state = TransferState.INVOICE_GENERATED

            self.db.commit()

            # Log state change
            self._log_state_change(
                transfer.id,
                old_state=TransferState.INITIATED,
                new_state=TransferState.INVOICE_GENERATED,
                reason=f"Invoice generated: {payment_hash[:16]}...",
                actor_type="system",
            )

            logger.info(f"Invoice generated for transfer: {transfer.reference}")

            return {
                "payment_hash": payment_hash,
                "payment_request": invoice["payment_request"],
                "invoice_expiry_at": expiry_at,
            }

        except Exception as e:
            logger.error(f"Failed to generate invoice: {e}")
            raise

    async def check_payment_received(
        self,
        transfer_id: uuid.UUID,
    ) -> bool:
        """
        Check if payment has been received

        Args:
            transfer_id: Transfer ID

        Returns:
            True if payment received, False otherwise
        """
        try:
            transfer = self.db.query(Transfer).filter(
                Transfer.id == transfer_id
            ).first()

            if not transfer or not transfer.invoice_hash:
                return False

            # Check invoice status
            is_paid = await self.lnd.check_invoice_paid(transfer.invoice_hash)

            if is_paid and transfer.state == TransferState.INVOICE_GENERATED:
                # Update transfer state
                transfer.state = TransferState.PAYMENT_LOCKED
                self.db.commit()

                self._log_state_change(
                    transfer.id,
                    old_state=TransferState.INVOICE_GENERATED,
                    new_state=TransferState.PAYMENT_LOCKED,
                    reason="Payment received and locked",
                    actor_type="system",
                )

                logger.info(f"Payment received for transfer: {transfer.reference}")

            return is_paid

        except Exception as e:
            logger.error(f"Error checking payment: {e}")
            return False

    async def verify_receiver(
        self,
        transfer_id: uuid.UUID,
        verified: bool = True,
    ) -> Transfer:
        """
        Mark receiver as verified

        Args:
            transfer_id: Transfer ID
            verified: Verification status

        Returns:
            Updated Transfer object
        """
        try:
            transfer = self.db.query(Transfer).filter(
                Transfer.id == transfer_id
            ).first()

            if not transfer:
                raise ValueError(f"Transfer {transfer_id} not found")

            transfer.receiver_phone_verified = verified
            transfer.verified_at = datetime.utcnow()

            # Transition state if both conditions met
            if (
                verified
                and transfer.state == TransferState.PAYMENT_LOCKED
                and transfer.agent_verified
            ):
                transfer.state = TransferState.RECEIVER_VERIFIED
                reason = "Receiver phone verified + agent verified"
                self._log_state_change(
                    transfer.id,
                    old_state=TransferState.PAYMENT_LOCKED,
                    new_state=TransferState.RECEIVER_VERIFIED,
                    reason=reason,
                    actor_type="system",
                )

            self.db.commit()
            logger.info(f"Receiver verified for transfer: {transfer.reference}")
            return transfer

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to verify receiver: {e}")
            raise

    async def verify_agent(
        self,
        transfer_id: uuid.UUID,
        verified: bool = True,
    ) -> Transfer:
        """
        Mark agent as verified

        Args:
            transfer_id: Transfer ID
            verified: Verification status

        Returns:
            Updated Transfer object
        """
        try:
            transfer = self.db.query(Transfer).filter(
                Transfer.id == transfer_id
            ).first()

            if not transfer:
                raise ValueError(f"Transfer {transfer_id} not found")

            transfer.agent_verified = verified

            # Transition state if all conditions met
            if (
                verified
                and transfer.state == TransferState.PAYMENT_LOCKED
                and transfer.receiver_phone_verified
            ):
                transfer.state = TransferState.RECEIVER_VERIFIED
                reason = "Agent verified + receiver phone verified"
                self._log_state_change(
                    transfer.id,
                    old_state=TransferState.PAYMENT_LOCKED,
                    new_state=TransferState.RECEIVER_VERIFIED,
                    reason=reason,
                    actor_type="system",
                )

            self.db.commit()
            logger.info(f"Agent verified for transfer: {transfer.reference}")
            return transfer

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to verify agent: {e}")
            raise

    async def execute_payout(
        self,
        transfer_id: uuid.UUID,
    ) -> Transfer:
        """
        Execute cash payout (settle hold invoice)

        Args:
            transfer_id: Transfer ID

        Returns:
            Updated Transfer object
        """
        try:
            transfer = self.db.query(Transfer).filter(
                Transfer.id == transfer_id
            ).first()

            if not transfer:
                raise ValueError(f"Transfer {transfer_id} not found")

            if transfer.state != TransferState.RECEIVER_VERIFIED:
                raise ValueError(
                    f"Cannot execute payout in state {transfer.state}"
                )

            # Generate preimage for invoice settlement
            preimage = secrets.token_hex(32)  # 32 bytes = 64 hex chars

            # Store preimage (should be encrypted in production)
            hold_record = InvoiceHold(
                id=uuid.uuid4(),
                invoice_hash=transfer.invoice_hash,
                transfer_id=transfer.id,
                preimage=preimage,  # TODO: Encrypt this
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )

            self.db.add(hold_record)
            self.db.commit()

            # Settle invoice
            await self.lnd.settle_invoice(preimage)

            # Update transfer
            transfer.state = TransferState.PAYOUT_EXECUTED
            transfer.payout_at = datetime.utcnow()
            self.db.commit()

            self._log_state_change(
                transfer.id,
                old_state=TransferState.RECEIVER_VERIFIED,
                new_state=TransferState.PAYOUT_EXECUTED,
                reason="Cash payout executed, invoice settled",
                actor_type="agent",
            )

            logger.info(f"Payout executed for transfer: {transfer.reference}")
            return transfer

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to execute payout: {e}")
            raise

    async def mark_settled(
        self,
        transfer_id: uuid.UUID,
    ) -> Transfer:
        """
        Mark transfer as fully settled (payout confirmed)

        Args:
            transfer_id: Transfer ID

        Returns:
            Updated Transfer object
        """
        try:
            transfer = self.db.query(Transfer).filter(
                Transfer.id == transfer_id
            ).first()

            if not transfer:
                raise ValueError(f"Transfer {transfer_id} not found")

            transfer.state = TransferState.SETTLED
            transfer.settled_at = datetime.utcnow()
            self.db.commit()

            self._log_state_change(
                transfer.id,
                old_state=TransferState.PAYOUT_EXECUTED,
                new_state=TransferState.SETTLED,
                reason="Transfer settled - payout confirmed by receiver",
                actor_type="receiver",
            )

            logger.info(f"Transfer settled: {transfer.reference}")
            return transfer

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark settled: {e}")
            raise

    async def refund_transfer(
        self,
        transfer_id: uuid.UUID,
        reason: str = "Unknown",
    ) -> Transfer:
        """
        Refund a transfer (reverse the payment)

        Args:
            transfer_id: Transfer ID
            reason: Refund reason

        Returns:
            Updated Transfer object
        """
        try:
            transfer = self.db.query(Transfer).filter(
                Transfer.id == transfer_id
            ).first()

            if not transfer:
                raise ValueError(f"Transfer {transfer_id} not found")

            # Can only refund if payment was locked
            if transfer.state not in [
                TransferState.INVOICE_GENERATED,
                TransferState.PAYMENT_LOCKED,
                TransferState.RECEIVER_VERIFIED,
            ]:
                raise ValueError(
                    f"Cannot refund transfer in state {transfer.state}"
                )

            transfer.state = TransferState.REFUNDED
            self.db.commit()

            self._log_state_change(
                transfer.id,
                old_state=transfer.state,
                new_state=TransferState.REFUNDED,
                reason=f"Refunded: {reason}",
                actor_type="system",
            )

            logger.info(f"Transfer refunded: {transfer.reference} - {reason}")
            return transfer

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to refund transfer: {e}")
            raise

    def _log_state_change(
        self,
        transfer_id: uuid.UUID,
        old_state: Optional[TransferState],
        new_state: TransferState,
        reason: str,
        actor_type: str,
    ) -> None:
        """Log state transition to audit trail"""
        try:
            history = TransferHistory(
                id=uuid.uuid4(),
                transfer_id=transfer_id,
                old_state=old_state,
                new_state=new_state,
                reason=reason,
                actor_type=actor_type,
            )
            self.db.add(history)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log state change: {e}")

    async def get_transfer(self, transfer_id: uuid.UUID) -> Optional[Transfer]:
        """Get transfer by ID"""
        return self.db.query(Transfer).filter(Transfer.id == transfer_id).first()

    async def get_transfer_by_reference(self, reference: str) -> Optional[Transfer]:
        """Get transfer by reference"""
        return self.db.query(Transfer).filter(Transfer.reference == reference).first()
